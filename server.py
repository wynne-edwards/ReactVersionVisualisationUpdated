import math
import re
from flask import Flask, request, send_from_directory, jsonify
import psycopg2
import pyodbc
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os
import squarify
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask_compress import Compress
import time
import copy

app = Flask(__name__, static_folder="client/build", static_url_path="")
Compress(app)

database_config = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'postgres',
    'host': '127.0.0.1',  # or your server's IP address
    'port': '5432'  # default PostgreSQL port
}

# Define a function to establish a connection to PostgreSQL
def get_postgres_connection():
    try:
        conn = psycopg2.connect(**database_config)
        print("Connected to PostgreSQL database")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        return None

output_svg_file = "../database/treemap.svg"
cache = {}
filter_data = {}  # Global variable to store filter data

class Site:
    def __init__(self, siteCode, siteName):
        self.siteCode = siteCode
        self.siteName = siteName
        self.buildings = []

    def add_building(self, building):
        self.buildings.append(building)

    def get_total_issue_count(self):
        return sum([b.get_total_issue_count() for b in self.buildings])

    def get_site_size(self):
        return sum([b.get_building_size() for b in self.buildings])

    def get_min_size(self):
        return max([b.get_building_size() for b in self.buildings])


class Building:
    def __init__(self, buildingCode, buildingName):
        self.buildingCode = buildingCode
        self.buildingName = buildingName
        self.floors = []

    def add_floor(self, floor):
        self.floors.append(floor)

    def get_total_issue_count(self):
        return sum([f.get_total_issue_count() for f in self.floors])

    def get_building_size(self):
        return sum([f.get_floor_size() for f in self.floors])

    def get_min_size(self):
        return max([f.get_floor_size() for f in self.floors])


class Floor:
    def __init__(self, floorCode, floorName):
        self.floorCode = floorCode
        self.floorName = floorName
        self.units = []

    def add_unit(self, unit):
        self.units.append(unit)

    def get_total_issue_count(self):
        return sum([u.issueCount for u in self.units])

    def get_floor_size(self):
        return sum([u.unitSize for u in self.units])

    def get_min_size(self):
        return max([u.unitSize for u in self.units])


class Unit:
    def __init__(self, unitCode, unitName, issueCount):
        self.unitCode = unitCode
        self.unitName = unitName
        self.issueCount = issueCount
        self.unitSize = 0

    def add_unit_size(self, size):
        self.unitSize = size


def extract_data_from_access(filters):
    conn = get_postgres_connection()
    if conn is None:
        raise Exception("Database connection failed.")

    query = """
    SELECT 
        "Location"."Building Code",
        "Building"."Building Name", 
        "Location"."Floor Code", 
        "Unit"."Unit Code", 
        "Site"."SiteCode",
        "Site"."SiteName", 
        "Floor"."Floor Name", 
        "Unit"."Unit Name", 
        COUNT("Combined"."Activity Log ID") as "IssueCount"
    FROM "Combined"
    INNER JOIN "Location" ON "Combined"."LocationID" = "Location"."LocationID"
    INNER JOIN "Unit" ON "Location"."UnitID" = "Unit"."UnitID"
    INNER JOIN "Building" ON "Location"."Building Code" = "Building"."Building Code"
    INNER JOIN "Site" ON "Location"."Site Code" = "Site"."SiteCode"
    INNER JOIN "Floor" ON "Location"."Floor Code" = "Floor"."Floor Code"
    INNER JOIN "Craftsperson" ON "Combined"."Craftsperson Code" = "Craftsperson"."Craftsperson Code"
    WHERE 1=1
    """

    if 'work_request_status' in filters and filters['work_request_status']:
        filters['work_request_status'] = filters['work_request_status'].split(',')
        query += "AND \"Combined\".\"Work Request Status\" IN ({})".format(
            ', '.join(f"'{status.strip()}'" for status in filters['work_request_status'])
        )

    if 'craftsperson_name' in filters and filters['craftsperson_name']:
        filters['craftsperson_name'] = filters['craftsperson_name'].split(',')
        query += "AND \"Craftsperson\".\"Craftsperson Name\" IN ({})".format(
            ', '.join(f"'{name.strip()}'" for name in filters['craftsperson_name'])
        )

    if 'primary_trade' in filters and filters['primary_trade']:
        filters['primary_trade'] = filters['primary_trade'].split(',')
        query += "AND \"Craftsperson\".\"Primary Trade\" IN ({})".format(
            ', '.join(f"'{trade.strip()}'" for trade in filters['primary_trade'])
        )

    if 'time_to_complete' in filters and filters['time_to_complete']:
        time_to_complete_filters = filters['time_to_complete'].split(',')
        for condition in time_to_complete_filters:
            if condition == "less_than_10":
                query += "AND (EXTRACT(EPOCH FROM \"Date and Time Issued\" - \"Date and Time Requested\")/86400) < 10 "
            elif condition == "10-30":
                query += "AND (EXTRACT(EPOCH FROM \"Date and Time Issued\" - \"Date and Time Requested\")/86400) BETWEEN 10 AND 30 "
            elif condition == "more_than_30":
                query += "AND (EXTRACT(EPOCH FROM \"Date and Time Issued\" - \"Date and Time Requested\")/86400) > 30 "

    query += """
    GROUP BY 
        "Location"."Building Code",
        "Building"."Building Name", 
        "Location"."Floor Code", 
        "Unit"."Unit Code",
        "Site"."SiteCode",
        "Site"."SiteName",
        "Floor"."Floor Name",
        "Unit"."Unit Name";
    """

    print(f"Executing query: {query}")
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    df = pd.DataFrame.from_records(rows, columns=[desc[0] for desc in cursor.description])
    return df


from concurrent.futures import ProcessPoolExecutor

def generate_treemap_data(df, level="site", parent_code=None, batch_size=1500, num_workers=16):
    sites = {}

    for batch in batch_iterator(df.itertuples(index=False, name=None), batch_size):
        for row in batch:
            siteCode = row[4]  # 'SiteCode'
            siteName = row[5]  # 'SiteName'
            buildingCode = row[0]  # 'Building Code'
            buildingName = row[1]  # 'Building Name'
            floorCode = row[2]  # 'Floor Code'
            floorName = row[6]  # 'Floor Name'
            unitCode = row[3]  # 'Unit Code'
            unitName = row[7]  # 'Unit Name'
            issueCount = row[8]  # 'IssueCount'

            site = sites.setdefault(siteCode, Site(siteCode, siteName))
            site_buildings = site.buildings_dict = getattr(site, 'buildings_dict', {})

            building = site_buildings.get(buildingCode)
            if not building:
                building = Building(buildingCode, buildingName)
                site.add_building(building)
                site_buildings[buildingCode] = building

            building_floors = building.floors_dict = getattr(building, 'floors_dict', {})

            floor = building_floors.get(floorCode)
            if not floor:
                floor = Floor(floorCode, floorName)
                building.add_floor(floor)
                building_floors[floorCode] = floor

            floor_units = floor.units_dict = getattr(floor, 'units_dict', {})

            unit = floor_units.get(unitCode)
            if not unit:
                unit = Unit(unitCode, unitName, issueCount)
                floor.add_unit(unit)
                floor_units[unitCode] = unit

    if level == "site":
        timestamp = time.time()
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {
                executor.submit(
                    calculate_and_add_unit_sizes_batch,
                    floor,
                    f"{site.siteCode}:{building.buildingCode}:{floor.floorCode}",
                ): floor
                for site in sites.values()
                for building in site.buildings
                for floor in building.floors
            }

            for future in as_completed(futures):
                floor_results = future.result()
                for unit_code, size in floor_results:
                    for site in sites.values():
                        for building in site.buildings:
                            for floor in building.floors:
                                if unit_code in floor.units_dict:
                                    floor.units_dict[unit_code].unitSize = size

        print(f"Time taken to calculate unit sizes: {time.time() - timestamp:.2f} seconds")

    return sites


def calculate_and_add_unit_sizes_batch(floor, parent_code):
    floor_results = calculate_unit_size(floor, parent_code)
    return floor_results


def batch_iterator(iterator, batch_size):
    batch = []
    for item in iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def generate_color_scale(df, column="IssueCount"):
    df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=[column])

    if df.empty:
        raise ValueError(
            f"No valid data in DataFrame after dropping NaNs in column '{column}'."
        )

    norm = plt.Normalize(df[column].min(), df[column].max())
    colors = plt.cm.Blues(norm(df[column]))
    df["Color"] = [mcolors.to_hex(color) for color in colors]

    return df


def create_building_plan_visualization(sites, parent_code, output_file, norm):
    print(f"Coloring units for {parent_code}...")
    site_code, building_code, floor_code = parent_code.split(":")
    svg_file = f"../database/Architectural Drawings/{site_code}-{building_code}-{floor_code}.svg"
    
    paths, texts, tree, root = parse_svg(svg_file)
    rooms = generate_room_associations(paths, texts)

    for room in rooms:
        id_parts = room["id"].split(";")
        if len(id_parts) >= 3:
            unit_code = id_parts[2].strip().lower()
        else:
            continue

        if unit_code.startswith("int") or unit_code.startswith("ext"):
            continue

        unit = next(
            (
                u
                for site in sites.values()
                for building in site.buildings
                for floor in building.floors
                for u in floor.units
                if u.unitCode.strip().lower() == unit_code
            ),
            None,
        )

        if unit:
            color = mcolors.to_hex(plt.cm.Blues(norm(unit.issueCount)))

            for path_elem, path_d, class_name, id_name in paths:
                room_parts = id_name.split(";")
                if len(room_parts) >= 3:
                    room_code = room_parts[2].strip().lower()
                else:
                    continue
                if room_code == unit_code:
                    path_elem.set("fill", color)
                    path_elem.set("class", "unit-room")
                    path_elem.set("data_name", unit.unitName)
                    path_elem.set("data_issues", str(unit.issueCount))
                    path_elem.set("data_size", str(unit.unitSize))

    tree.write(output_file)


def create_interactive_treemap(sites, level, output_file, width, height, min_size=200):
    svg_ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", svg_ns)

    new_svg = ET.Element(
        "svg",
        xmlns=svg_ns,
        viewBox=f"0 0 {width} {height}",
        width="100%",
        height="100%",
    )
    x, y = 0, 0
    site_rects = []

    if level == "site":
        all_issues = [site.get_total_issue_count() for site in sites.values()]
        norm = plt.Normalize(min(all_issues), max(all_issues))
        min_size = max([site.get_min_size() for site in sites.values()])
        for site_code, site in sites.items():
            site_size = site.get_site_size()
            site_issues = site.get_total_issue_count()
            color = mcolors.to_hex(plt.cm.Blues(norm(site_issues)))

            site_rect = {
                "id": site_code,
                "value": max(site_size, min_size * (1 / 10)),
                "color": color,
                "name": site.siteName,
                "issues": site_issues,
                "size": site_size,
            }
            site_rects.append(site_rect)

    elif level == "building":
        all_issues = [
            building.get_total_issue_count()
            for site in sites.values()
            for building in site.buildings
        ]
        norm = plt.Normalize(min(all_issues), max(all_issues))
        min_size = max(
            [
                building.get_min_size()
                for site in sites.values()
                for building in site.buildings
            ]
        )
        for site_code, site in sites.items():
            for building in site.buildings:
                building_size = building.get_building_size()
                building_issues = building.get_total_issue_count()
                color = mcolors.to_hex(plt.cm.Blues(norm(building_issues)))

                building_rect = {
                    "id": f"{site_code}:{building.buildingCode}",
                    "value": max(building_size, min_size * (1 / 10)),
                    "color": color,
                    "name": building.buildingName,
                    "issues": building_issues,
                    "size": building_size,
                }
                site_rects.append(building_rect)

    elif level == "floor":
        all_issues = [
            floor.get_total_issue_count()
            for site in sites.values()
            for building in site.buildings
            for floor in building.floors
        ]
        norm = plt.Normalize(min(all_issues), max(all_issues))
        min_size = max(
            [
                floor.get_min_size()
                for site in sites.values()
                for building in site.buildings
                for floor in building.floors
            ]
        )
        for site_code, site in sites.items():
            for building in site.buildings:
                for floor in building.floors:
                    floor_size = floor.get_floor_size()
                    floor_issues = floor.get_total_issue_count()
                    color = mcolors.to_hex(plt.cm.Blues(norm(floor_issues)))

                    floor_rect = {
                        "id": f"{site_code}:{building.buildingCode}:{floor.floorCode}",
                        "value": max(floor_size, min_size * (1 / 10)),
                        "color": color,
                        "name": floor.floorName,
                        "issues": floor_issues,
                        "size": floor_size,
                    }
                    site_rects.append(floor_rect)

    elif level == "unit":
        all_issues = [
            unit.issueCount
            for site in sites.values()
            for building in site.buildings
            for floor in building.floors
            for unit in floor.units
        ]
        norm = plt.Normalize(min(all_issues), max(all_issues))
        min_size = max(
            [
                unit.unitSize
                for site in sites.values()
                for building in site.buildings
                for floor in building.floors
                for unit in floor.units
            ]
        )
        for site_code, site in sites.items():
            for building in site.buildings:
                for floor in building.floors:
                    for unit in floor.units:
                        unit_size = unit.unitSize
                        unit_issues = unit.issueCount
                        color = mcolors.to_hex(plt.cm.Blues(norm(unit_issues)))

                        unit_rect = {
                            "id": f"{site_code}:{building.buildingCode}:{floor.floorCode}:{unit.unitCode}",
                            "value": max(unit_size, min_size * (1 / 4)),
                            "color": color,
                            "name": unit.unitName,
                            "issues": unit_issues,
                            "size": unit_size,
                        }
                        site_rects.append(unit_rect)

    sizes = [rect["value"] for rect in site_rects]
    if 0 in sizes:
        sizes = [size if size > 0 else 1 for size in sizes]
    norm_sizes = squarify.normalize_sizes(sizes, width, height)
    rects = squarify.padded_squarify(norm_sizes, x, y, width, height)

    for rect, site_rect in zip(rects, site_rects):
        group_elem = ET.Element("g")

        elem = ET.Element(
            "rect",
            x=str(rect["x"]),
            y=str(rect["y"]),
            width=str(rect["dx"]),
            height=str(rect["dy"]),
            fill=site_rect["color"],
            id=site_rect["id"],
            stroke="black",
            stroke_width="1",
            data_name=site_rect["name"],
            data_issues=str(site_rect["issues"]),
            data_size=str(site_rect["size"]),
        )
        if level == "site":
            elem.set("class", "site")
        elif level == "building":
            elem.set("class", "building")
        elif level == "floor":
            elem.set("class", "floor")
        elif level == "unit":
            elem.set("class", "unit")
        group_elem.append(elem)

        new_svg.append(group_elem)

    tree = ET.ElementTree(new_svg)
    with open(output_file, "wb") as f:
        tree.write(f, xml_declaration=True, encoding="utf-8")


def calculate_unit_size(floor, parent_code):
    site_code, building_code, floor_code = parent_code.split(":")
    svg_file = f"../database/Architectural Drawings/{site_code}-{building_code}-{floor_code}.svg"
    
    try:
        paths, texts, tree, root = parse_svg(svg_file)
        min_size = 50  # Default size for units if no match is found later on
        closed_paths = identify_closed_paths(paths, min_size)
        room_associations = generate_room_associations(closed_paths, texts)

        unit_sizes = []
        for unit in floor.units:
            matched = False
            for assoc in room_associations:
                try:
                    if (
                        assoc["id"].strip().lower().split(";")[2]
                        == unit.unitCode.strip().lower()
                    ):
                        unit_size = assoc["length"]
                        unit_sizes.append((unit.unitCode, unit_size))
                        matched = True
                        break
                except IndexError:
                    continue
            if not matched:
                unit_sizes.append((unit.unitCode, min_size))

        return unit_sizes

    except FileNotFoundError:
        return [(unit.unitCode, 50) for unit in floor.units]


def find_paths_and_texts(element, depth=0):
    paths = []
    texts = []
    if element.tag.endswith("path"):
        d = element.attrib.get("d", "N/A")
        class_name = element.attrib.get("class", "N/A")
        id_name = element.attrib.get("id", "N/A")
        paths.append((element, d, class_name, id_name))
    if element.tag.endswith("text"):
        text_content = element.text
        x = float(element.attrib.get("x", "0"))
        y = float(element.attrib.get("y", "0"))
        texts.append((element, text_content, x, y))
    for child in element:
        paths_and_texts = find_paths_and_texts(child, depth + 1)
        paths.extend(paths_and_texts[0])
        texts.extend(paths_and_texts[1])
    return paths, texts


def calculate_path_length(d):
    segments = re.findall(r"[MmLlHhVvZz]|[-+]?\d*\.\d+|[-+]?\d+", d)
    current_pos = (0, 0)
    start_pos = (0, 0)
    length = 0
    i = 0

    while i < len(segments):
        command = segments[i]

        if command in "Mm":
            x = float(segments[i + 1])
            y = float(segments[i + 2])
            if command == "m":
                x += current_pos[0]
                y += current_pos[1]
            start_pos = (x, y)
            current_pos = (x, y)
            i += 3

        elif command in "Ll":
            x = float(segments[i + 1])
            y = float(segments[i + 2])
            if command == "l":
                x += current_pos[0]
                y += current_pos[1]
            length += math.sqrt((x - current_pos[0]) ** 2 + (y - current_pos[1]) ** 2)
            current_pos = (x, y)
            i += 3

        elif command in "Hh":
            x = float(segments[i + 1])
            if command == "h":
                x += current_pos[0]
            length += abs(x - current_pos[0])
            current_pos = (x, current_pos[1])
            i += 2

        elif command in "Vv":
            y = float(segments[i + 1])
            if command == "v":
                y += current_pos[1]
            length += abs(y - current_pos[1])
            current_pos = (current_pos[0], y)
            i += 2

        elif command in "Zz":
            length += math.sqrt(
                (start_pos[0] - current_pos[0]) ** 2
                + (start_pos[1] - current_pos[1]) ** 2
            )
            current_pos = start_pos
            i += 1

        else:
            i += 1
    return length


def parse_svg(file):
    tree = ET.parse(file)
    root = tree.getroot()
    paths, texts = find_paths_and_texts(root)
    return paths, texts, tree, root


def get_path_bounds(d):
    numbers = list(map(float, re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", d)))
    xs = numbers[::2]
    ys = numbers[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def is_closed_path(d):
    return d.lower().strip().endswith("z")


def identify_closed_paths(paths, min_size):
    closed_paths = []
    for path in paths:
        d = path[1]
        if is_closed_path(d):
            x0, y0, x1, y1 = get_path_bounds(d)
            width = x1 - x0
            height = y1 - y0
            if width >= min_size and height >= min_size:
                closed_paths.append(path)
    return closed_paths


def generate_room_associations(paths, texts):
    associations = []
    for idx, (path_element, d, class_name, id_name) in enumerate(paths):

        if id_name.lower().startswith("int") or id_name.lower().startswith("ext"):
            continue

        nearest_text = None
        min_distance = float("inf")

        for text_element, room_name, x, y in texts:
            x0, y0, x1, y1 = get_path_bounds(d)
            path_center_x = (x0 + x1) / 2
            path_center_y = (y0 + y1) / 2
            distance = math.sqrt((x - path_center_x) ** 2 + (y - path_center_y) ** 2)

            if distance < min_distance:
                min_distance = distance
                nearest_text = (room_name, x, y)

        if nearest_text:
            room_name, x, y = nearest_text
        else:
            room_name = f"Room {idx + 1}"
            x, y = 0, 0

        length = calculate_path_length(d)
        associations.append(
            {
                "room_name": room_name,
                "path": d,
                "class": class_name,
                "id": id_name,
                "text_x": x,
                "text_y": y,
                "length": length,
            }
        )
    return associations


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

full_hierarchy = None

def generate_full_hierarchy(df):
    global full_hierarchy
    full_hierarchy = generate_treemap_data(df)
    
def filter_hierarchy(parent_code, level):
    if full_hierarchy is None:
        return {}

    filtered_sites = {}

    if level == "site":
        return copy.deepcopy(full_hierarchy)

    elif level == "building":
        site = copy.deepcopy(full_hierarchy.get(parent_code))
        if site:
            filtered_sites[parent_code] = site

    elif level == "floor":
        site_code, building_code = parent_code.split(":")
        site = copy.deepcopy(full_hierarchy.get(site_code))
        if site:
            building = next((b for b in site.buildings if b.buildingCode == building_code), None)
            if building:
                site.buildings = [building]
                filtered_sites[site_code] = site

    elif level == "unit":
        site_code, building_code, floor_code = parent_code.split(":")
        site = copy.deepcopy(full_hierarchy.get(site_code))
        if site:
            building = next((b for b in site.buildings if b.buildingCode == building_code), None)
            if building:
                floor = next((f for f in building.floors if f.floorCode == floor_code), None)
                if floor:
                    building.floors = [floor]
                    site.buildings = [building]
                    filtered_sites[site_code] = site

    return filtered_sites


@app.route("/generate_svg", methods=["GET"])
def generate_svg():
    level = request.args.get("level")
    parent_code = request.args.get("parent_code")
    visualization_type = request.args.get("visualization_type", "squarified")
    width = int(request.args.get("width", 1920))
    height = int(request.args.get("height", 930))

    filters = {}
    work_request_status = request.args.get("work_request_status")
    requested_by = request.args.get("requested_by")
    craftsperson_name = request.args.get("craftsperson_name")
    primary_trade = request.args.get("primary_trade")
    time_to_complete = request.args.get("time_to_complete")

    if work_request_status:
        filters["work_request_status"] = work_request_status
    if requested_by:
        filters["requested_by"] = requested_by
    if craftsperson_name:
        filters["craftsperson_name"] = craftsperson_name
    if primary_trade:
        filters["primary_trade"] = primary_trade
    if time_to_complete:
        filters["time_to_complete"] = time_to_complete

    cache_key = f"{level}-{parent_code}-{visualization_type}-{filters}"

    use_cache = not bool(filters)  # Use cache only if no filters are applied
    if use_cache and cache_key in cache:
        svg_content = cache[cache_key]["svg_content"]
    else:
        df = extract_data_from_access(filters)
        if df.empty:
            return jsonify({"error": "No data found for the selected filters."}), 404
        df = generate_color_scale(df)
        if df.empty:
            return jsonify({"error": "No valid data after applying color scale."}), 404

        if not use_cache:
            generate_full_hierarchy(df)
             
        if level == "site" and (full_hierarchy is None):
            generate_full_hierarchy(df)

        filtered_hierarchy = filter_hierarchy(parent_code, level)

        if filtered_hierarchy:
            if visualization_type == "squarified" or (visualization_type == "building-plans" and level != "unit"):
                create_interactive_treemap(
                    filtered_hierarchy, level, output_svg_file, width, height
                )
            elif visualization_type == "building-plans" and level == "unit":
                try:
                    min_size = min(
                        [
                            unit.unitSize
                            for site in filtered_hierarchy.values()
                            for building in site.buildings
                            for floor in building.floors
                            for unit in floor.units
                        ]
                    )
                    issue_counts = [
                        u.issueCount
                        for site in filtered_hierarchy.values()
                        for building in site.buildings
                        for floor in building.floors
                        for u in floor.units
                    ]
                    norm = plt.Normalize(min(issue_counts), max(issue_counts))

                    create_building_plan_visualization(
                        filtered_hierarchy, parent_code, output_svg_file, norm
                    )

                except FileNotFoundError:
                    return jsonify({"error": "SVG file not found for the specified floor."}), 404
            else:
                return "Invalid level", 400

        with open(output_svg_file, "r") as f:
            svg_content = f.read()

        if use_cache:
            cache[cache_key] = {"svg_content": svg_content, "filters": filters}

    return svg_content


@app.route("/clear_cache_and_filters", methods=["POST"])
def clear_cache_and_filters():
    try:
        global full_hierarchy
        # Clear the in-memory cache
        cache.clear()
        
        # Reset the hierarchy data to ensure filters are cleared
        full_hierarchy = None
        
        return "Filters and cache cleared successfully", 200
    except Exception as e:
        return f"Error clearing filters and cache: {str(e)}", 500



@app.route("/get_filter_options", methods=["GET"])
def get_filter_options():
    conn = get_postgres_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed."}), 500

    options = {
        "work_request_status": [],
        "requested_by": [],
        "craftsperson_name": [],
        "primary_trade": [],
    }

    try:
        cursor = conn.cursor()

        cursor.execute('SELECT DISTINCT "Work Request Status" FROM "Combined"')
        options["work_request_status"] = [row[0] for row in cursor.fetchall()]

        cursor.execute('SELECT DISTINCT "Requested by" FROM "Combined"')
        options["requested_by"] = [row[0] for row in cursor.fetchall()]

        cursor.execute('SELECT DISTINCT "Craftsperson Name" FROM "Craftsperson"')
        options["craftsperson_name"] = [row[0] for row in cursor.fetchall()]

        cursor.execute('SELECT DISTINCT "Primary Trade" FROM "Craftsperson"')
        options["primary_trade"] = [row[0] for row in cursor.fetchall()]

    except psycopg2.Error as e:
        error_message = f"Database query error: {str(e)}"
        print(error_message)
        return jsonify({"error": error_message}), 500
    finally:
        conn.close()

    return jsonify(options)


@app.route("/get_unit_problems", methods=["GET"])
def get_unit_problems():
    code = request.args.get("unit_code")

    work_request_status = request.args.get("work_request_status")
    craftsperson_name = request.args.get("craftsperson_name")
    primary_trade = request.args.get("primary_trade")

    print("Unit code: ", code)

    if not code:
        return "Unit code is required", 400

    site_code = ""
    if len(code.split(":")) == 4:
        site_code, building_code, floor_code, unit_code = code.split(":")
    elif len(code.split(";")) == 3:
        building_code, floor_code, unit_code = code.split(";")

    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
    except psycopg2.Error as e:
        error_message = f"Database connection error: {str(e)}"
        print(error_message)
        return error_message, 500

    query = """
    SELECT 
        "Combined"."Activity Log ID", 
        "Combined"."Work Description"
    FROM "Combined"
    INNER JOIN "Location" ON "Combined"."LocationID" = "Location"."LocationID"
    INNER JOIN "Unit" ON "Location"."UnitID" = "Unit"."UnitID"
    WHERE 1=1
    """

    if site_code != "":
        query += f'AND "Location"."Site Code" = \'{site_code}\' AND "Location"."Building Code" = \'{building_code}\' AND "Location"."Floor Code" = \'{floor_code}\' AND "Unit"."Unit Code" = \'{unit_code}\''
    else:
        query += f'AND "Location"."Building Code" = \'{building_code}\' AND "Location"."Floor Code" = \'{floor_code}\' AND "Unit"."Unit Code" = \'{unit_code}\''

    if work_request_status:
        statuses = work_request_status.split(",")
        status_list = ", ".join([f"'{status.strip()}'" for status in statuses])
        query += f' AND "Combined"."Work Request Status" IN ({status_list})'

    if craftsperson_name:
        names = craftsperson_name.split(",")
        name_list = ", ".join([f"'{name.strip()}'" for name in names])
        query += f' AND "Craftsperson"."Craftsperson Name" IN ({name_list})'

    if primary_trade:
        trades = primary_trade.split(",")
        trade_list = ", ".join([f"'{trade.strip()}'" for trade in trades])
        query += f' AND "Craftsperson"."Primary Trade" IN ({trade_list})'

    try:
        print("Executing ", query)
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        problems = [{"log_id": row[0], "description": row[1]} for row in rows]
        return jsonify(problems)
    except psycopg2.Error as e:
        error_message = f"Database query error: {str(e)}"
        print(error_message)
        return error_message, 500
    except Exception as e:
        error_message = f"General error: {str(e)}"
        print(error_message)
        return error_message, 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)
