import math
import re
from flask import Flask, request, send_from_directory, jsonify
import pyodbc
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import os
import squarify
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed


app = Flask(__name__, static_folder="client/build", static_url_path="")

database_file = (
    "../database/Backup of CleanRhodesMaintenanceBackupV3.accdb"  # Database file path
)
output_svg_file = (
    "../database/treemap.svg"  # Temp, I have no idea if this is even required anymore.
)
cache = {}
if os.path.exists(database_file):
    print(f"File exists at: {database_file}")
else:
    print(f"File not found. Check the path: {database_file}")
try:
    with open(database_file, "rb") as f:
        print("File opened successfully")
except Exception as e:
    print(f"Failed to open file: {e}")


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
    """
    Extract data from the Access database based on the specified filters.

    :param: filters - A dictionary containing the filters to be applied to the data.

    :return: A DataFrame containing the extracted data.
    """
    
    conn_str = (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        r'DBQ=' + database_file + ';'
    )
    conn = pyodbc.connect(conn_str)
    query = """
    SELECT 
        Location.[Building Code],
        Building.[Building Name], 
        Location.[Floor Code], 
        Unit.[Unit Code], 
        Site.[SiteCode],
        Site.[SiteName], 
        Floor.[Floor Name], 
        Unit.[Unit Name], 
        COUNT(Combined.[Activity Log ID]) as IssueCount
    FROM (((((Combined
    INNER JOIN Location ON Combined.LocationID = Location.LocationID)
    INNER JOIN Unit ON Location.UnitID = Unit.UnitID)
    INNER JOIN Building ON Location.[Building Code] = Building.[Building Code])
    INNER Join Site ON Location.[Site Code] = Site.[SiteCode])
    INNER JOIN Floor ON Location.[Floor Code] = Floor.[Floor Code])
    INNER JOIN Craftsperson ON Combined.[Craftsperson Code] = Craftsperson.[Craftsperson Code]
    WHERE 1=1
    """

    if 'work_request_status' in filters and filters['work_request_status']:
        filters['work_request_status'] = filters['work_request_status'].split(',')
        query += "AND Combined.[Work Request Status] IN ({})".format(
            ', '.join(f"'{status.strip()}'" for status in filters['work_request_status'])
        )

    if 'craftsperson_name' in filters and filters['craftsperson_name']:
        filters['craftsperson_name'] = filters['craftsperson_name'].split(',')
        query += "AND Craftsperson.[Craftsperson Name] IN ({})".format(
            ', '.join(f"'{name.strip()}'" for name in filters['craftsperson_name'])
        )

    if 'primary_trade' in filters and filters['primary_trade']:
        filters['primary_trade'] = filters['primary_trade'].split(',')
        query += "AND Craftsperson.[Primary Trade] IN ({})".format(
            ', '.join(f"'{trade.strip()}'" for trade in filters['primary_trade'])
        )
    if 'time_to_complete' in filters and filters['time_to_complete']:
        time_to_complete_filters = filters['time_to_complete'].split(',')
        for condition in time_to_complete_filters:
            if condition == "less_than_10":
                query += "AND DATEDIFF('d', [Date and Time Requested], [Date and Time Issued]) < 10 "
            elif condition == "10-30":
                query += "AND DATEDIFF('d', [Date and Time Requested], [Date and Time Issued]) BETWEEN 10 AND 30 "
            elif condition == "more_than_30":
                query += "AND DATEDIFF('d', [Date and Time Requested], [Date and Time Issued]) > 30 "

    query += """
    GROUP BY 
        Location.[Building Code],
        Building.[Building Name], 
        Location.[Floor Code], 
        Unit.[Unit Code],
        Site.[SiteCode],
        Site.[SiteName],
        Floor.[Floor Name],
        Unit.[Unit Name];
    """

    print(f"Executing query: {query}")
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    df = pd.DataFrame.from_records(rows, columns=[desc[0] for desc in cursor.description])
    return df



def generate_treemap_data(df):
    """
    Populates the classes with their hierarchical subclasses and calculates the sizes of the units through the help of multithreading for increased speed.

    :param: df -  The DataFrame containing the data to be used for generating the treemap.

    :return: sites - A class that contains the subclasses of building, floor & unit with their respective attributes as found in the classes.
    """
    sites = {}
    for _, row in df.iterrows():
        siteCode = row["SiteCode"]
        siteName = row["SiteName"]
        buildingCode = row["Building Code"]
        buildingName = row["Building Name"]
        floorCode = row["Floor Code"]
        floorName = row["Floor Name"]
        unitCode = row["Unit Code"]
        unitName = row["Unit Name"]
        issueCount = row["IssueCount"]

        site = sites.setdefault(siteCode, Site(siteCode, siteName))
        building = next(
            (b for b in site.buildings if b.buildingCode == buildingCode), None
        )
        if not building:
            building = Building(buildingCode, buildingName)
            site.add_building(building)

        floor = next((f for f in building.floors if f.floorCode == floorCode), None)
        if not floor:
            floor = Floor(floorCode, floorName)
            building.add_floor(floor)

        unit = next((u for u in floor.units if u.unitCode == unitCode), None)
        if not unit:
            unit = Unit(unitCode, unitName, issueCount)
            floor.add_unit(unit)

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                calculate_and_add_unit_sizes,
                floor,
                f"{site.siteCode}:{building.buildingCode}:{floor.floorCode}",
            ): floor
            for site in sites.values()
            for building in site.buildings
            for floor in building.floors
        }
        for future in as_completed(futures):
            future.result()

    return sites


def generate_color_scale(df, column="IssueCount"):
    """
    Generates a color scale for the specified column in the DataFrame. based on the IssueCount column by default.
    
    :param: df - The DataFrame containing the data to be used for generating the color scale.
    :param: column - The column in the DataFrame to be used for generating the color scale. Defaults to IssueCount

    :return: df -The DataFrame with the color scale generated for the specified column.
    """
    # Convert the specified column to numeric, forcing errors to NaN
    df[column] = pd.to_numeric(df[column], errors="coerce")

    # Drop rows where the column is NaN, as they can't be processed for color scaling
    df = df.dropna(subset=[column])

    if df.empty:
        raise ValueError(
            f"No valid data in DataFrame after dropping NaNs in column '{column}'."
        )

    norm = plt.Normalize(df[column].min(), df[column].max())
    colors = plt.cm.Blues(norm(df[column]))
    df["Color"] = [mcolors.to_hex(color) for color in colors]

    return df


def create_building_plan_visualization(sites, svg_file, output_file, norm):
    """
    Creates a building plan visualization based on the specified SVG file and the data from the sites. Different from create_interactive_treemap in that it colors the units in the **building plan** instead of a squarified treemap
    
    :param: sites - A class that contains the subclasses of building, floor & unit with their respective attributes as found in the classes.
    :param: svg_file - The path to the SVG file containing the building plan.
    :param: output_file - The path to the output SVG file to be generated.
    :param: norm - The color normalization function to be used for coloring the units based on the issue count.
"""
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
    """
    Creates an interactive squarified treemap visualization based on the specified sites and level.

    :param: sites - A class that contains the subclasses of building, floor & unit with their respective attributes as found in the classes.
    :param: level - The level of the treemap to be generated. Can be one of 'site', 'building', 'floor', or 'unit'.
    :param: output_file - The path to the output SVG file to be generated.
    :param: width - The width of the SVG file to be generated.
    :param: height - The height of the SVG file to be generated.
    :param: min_size - The minimum size of the treemap squares. Defaults to 200.
    """
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


# Calculate the size of a unit based on the building plan
def calculate_unit_size(floor, parent_code):
    """
    Calculates the size of a unit based on the size of the unit in the building plan. This flows up as it effects the size of the floor, building, and site.
    
    :param: floor - The floor object containing the units to be sized.
    :param: parent_code - The parent code of the floor to be used for finding the building plan.
    
    :return unit_sizes:  - A list of tuples containing the unit code and the calculated size of the unit."""

    site_code, building_code, floor_code = parent_code.split(":")

    try:
        paths, texts, tree, root = parse_svg(
            f"../database/Architectural Drawings/{site_code}-{building_code}-{floor_code}.svg"
        )

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

        # Add any units from the building plan that are not in the database
        for assoc in room_associations:
            try:
                unit_code = assoc["id"].strip().lower().split(";")[2]
                if unit_code.startswith("int") or unit_code.startswith("ext"):
                    continue  # Ignore IDs starting with int or ext
                if not any(
                    unit.unitCode.strip().lower() == unit_code for unit in floor.units
                ):
                    unit_size = assoc["length"]
                    unit_sizes.append((unit_code, unit_size))
                    new_unit = Unit(unit_code, assoc["room_name"], 0)
                    floor.add_unit(new_unit)
            except IndexError:
                continue

        return unit_sizes
    except FileNotFoundError:
        return [(unit.unitCode, 50) for unit in floor.units]


def calculate_and_add_unit_sizes(floor, parent_code):
    """
    Calculates the size of the units in the floor and adds them to the floor object. This function is basically a wrapper around calculate_unit_size and add_unit_size.
    
    :param: floor - The floor object containing the units to be sized.
    :param: parent_code - The parent code of the floor to be used for finding the building plan.
    """

    unit_sizes = calculate_unit_size(floor, parent_code)
    for unit_code, unit_size in unit_sizes:
        for unit in floor.units:
            if unit.unitCode == unit_code:
                unit.add_unit_size(unit_size)
                break


# Function to recursively find all path elements and text elements in the SVG with detailed attributes
def find_paths_and_texts(element, depth=0):
    """
    Recursively finds all path elements and text elements in the SVG with detailed attributes by looping through the XML tree.
    
    :param: element - The current element in the XML tree to be processed.
    :param: depth - The depth of the current element in the XML tree.
    
    :return paths:  - A list of tuples containing the path element and its attributes.
    :return texts:  - A list of tuples containing the text element and its attributes.
    """

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


# Function to calculate the total length of the path
def calculate_path_length(d):
    """
    Calculates the total length of the path by parsing the path data and calculating the length of each segment.
    
    :param: d - The path data string to be parsed.
    
    :return length:  - The total length of the path."""
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


# Parse SVG and extract path elements and text elements
def parse_svg(file):
    """
    Runs the relevent functions to parse the SVG file and extract the path elements and text elements.

    :param: file - The path to the SVG file to be parsed.

    :return paths:  - A list of tuples containing the path element and its attributes.
    :return texts:  - A list of tuples containing the text element and its attributes.
    :return tree:  - The ElementTree object containing the parsed SVG file.
    :return root:  - The root element of the parsed SVG file.
    """
    tree = ET.parse(file)
    root = tree.getroot()
    paths, texts = find_paths_and_texts(root)
    return paths, texts, tree, root


def get_path_bounds(d):
    """
    Gets the bounds of the path by parsing the path data and extracting the minimum and maximum x and y coordinates.

    :param: d - The path data string to be parsed.

    :return x0:  - The minimum x-coordinate of the path.
    :return y0:  - The minimum y-coordinate of the path.
    :return x1:  - The maximum x-coordinate of the path.
    :return y1:  - The maximum y-coordinate of the path.
    """
    numbers = list(map(float, re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", d)))
    xs = numbers[::2]
    ys = numbers[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def is_closed_path(d):
    return d.lower().strip().endswith("z")


# Identify closed paths larger than a specific size
def identify_closed_paths(paths, min_size):
    """
    Identifies closed paths larger than a specific size by checking if the path is closed and if the width and height of the path are greater than the specified minimum size.
    
    :param: paths - A list of tuples containing the path element and its attributes.
    :param: min_size - The minimum size of the paths to be considered.
    
    :return closed_paths:  - A list of tuples containing the closed path elements and their attributes.
    """

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


# Generate a list of room associations with paths and texts
def generate_room_associations(paths, texts):
    """
    Generates a list of room associations with paths and texts by finding the nearest text element to each path element and associating them together.
    
    :param: paths - A list of tuples containing the path element and its attributes.
    :param: texts - A list of tuples containing the text element and its attributes.
    
    :return associations:  - A list of dictionaries containing the room name, path, class, id, text x-coordinate, text y-coordinate, and length of the path.
"""
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


@app.route("/generate_svg", methods=["GET"])
def generate_svg():
    """
    Generates an SVG file based on the specified parameters and returns the SVG content as a response to display on the frontend
    
    :return svg: - The SVG content to be displayed on the frontend.
    """

    # Get all the parameters from the request such as codes and filters
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

    # Add filters to the dictionary if they are present in the request
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

    cache_key = f"{level}-{parent_code}-{filters}-{visualization_type}"

    if cache_key in cache:
        svg_content = cache[cache_key]["svg_content"]
    else:
        # If the cache key is not found, fetch the data from the database using the specified filters
        df = extract_data_from_access(filters)
        if df.empty:
            return jsonify({"error": "No data found for the selected filters."}), 404
        # Generate the color scale for the data based on the issue count
        df = generate_color_scale(df)
        if df.empty:
            return jsonify({"error": "No valid data after applying color scale."}), 404

        hierarchy = df

        # If we want a squarified treemap visualization go down this, however for the first 3 levels they would be identical only the unit level differs.
        if visualization_type == "squarified":
            if level == "site":
                sites = generate_treemap_data(hierarchy) #Populate the objects with the data
                min_size = min([site.get_site_size() for site in sites.values()])
            elif level == "building":
                hierarchy = df[df["SiteCode"] == parent_code] #As we no longer need sites, we only populate the next level with the data that would exist in that site.
                # I.E if we have clicked on precinct RU0001 only populate the buidlings, floors and units that could exist in that site.
                sites = generate_treemap_data(hierarchy)
                min_size = min(
                    [
                        building.get_building_size()
                        for site in sites.values()
                        for building in site.buildings
                    ]
                )
            elif level == "floor": #Same as above but for floors
                site_code, building_code = parent_code.split(":")
                hierarchy = df[
                    (df["SiteCode"] == site_code)
                    & (df["Building Code"] == building_code)
                ]
                sites = generate_treemap_data(hierarchy)
                min_size = min(
                    [
                        floor.get_floor_size()
                        for site in sites.values()
                        for building in site.buildings
                        for floor in building.floors
                    ]
                )
            elif level == "unit": #Same as above but for units
                site_code, building_code, floor_code = parent_code.split(":")
                hierarchy = df[
                    (df["SiteCode"] == site_code)
                    & (df["Building Code"] == building_code)
                    & (df["Floor Code"] == floor_code)
                ]
                sites = generate_treemap_data(hierarchy)
                min_size = min(
                    [
                        unit.unitSize
                        for site in sites.values()
                        for building in site.buildings
                        for floor in building.floors
                        for unit in floor.units
                    ]
                )
            else:
                return "Invalid level", 400

            # As the if statements would fill out the variables we only run this one function to create the treemap.
            create_interactive_treemap( 
                sites, level, output_svg_file, width, height, min_size=min_size
            )

        # If we want a building plan visualization go down this path
        elif visualization_type == "building-plans":
            if level == "site":
                sites = generate_treemap_data(hierarchy)
                min_size = min([site.get_site_size() for site in sites.values()])
                create_interactive_treemap(
                    sites, level, output_svg_file, width, height, min_size=min_size
                )
            elif level == "building":
                hierarchy = df[df["SiteCode"] == parent_code]
                sites = generate_treemap_data(hierarchy)
                min_size = min(
                    [
                        building.get_building_size()
                        for site in sites.values()
                        for building in site.buildings
                    ]
                )
                create_interactive_treemap(
                    sites, level, output_svg_file, width, height, min_size=min_size
                )
            elif level == "floor":
                site_code, building_code = parent_code.split(":")
                hierarchy = df[
                    (df["SiteCode"] == site_code)
                    & (df["Building Code"] == building_code)
                ]
                sites = generate_treemap_data(hierarchy)
                min_size = min(
                    [
                        floor.get_floor_size()
                        for site in sites.values()
                        for building in site.buildings
                        for floor in building.floors
                    ]
                )
                create_interactive_treemap(
                    sites, level, output_svg_file, width, height, min_size=min_size
                )
                #At the unit level we populate a building plan instead of a treemap
            elif level == "unit":
                site_code, building_code, floor_code = parent_code.split(":")
                hierarchy = df[
                    (df["SiteCode"] == site_code)
                    & (df["Building Code"] == building_code)
                    & (df["Floor Code"] == floor_code)
                ]
                sites = generate_treemap_data(hierarchy)
                # fetching the building plan
                svg_file = f"../database/Architectural Drawings/{site_code}-{building_code}-{floor_code}.svg"
                try:
                    min_size = min(
                        [
                            unit.unitSize
                            for site in sites.values()
                            for building in site.buildings
                            for floor in building.floors
                            for unit in floor.units
                        ]
                    )
                    issue_counts = [
                        u.issueCount
                        for site in sites.values()
                        for building in site.buildings
                        for floor in building.floors
                        for u in floor.units
                    ]
                    norm = plt.Normalize(min(issue_counts), max(issue_counts))

                    # Populate the svg
                    create_building_plan_visualization(
                        sites, svg_file, output_svg_file, norm
                    )

                except FileNotFoundError:
                    site_code, building_code, floor_code = parent_code.split(":")
                    hierarchy = df[
                        (df["SiteCode"] == site_code)
                        & (df["Building Code"] == building_code)
                        & (df["Floor Code"] == floor_code)
                    ]
                    sites = generate_treemap_data(hierarchy)
                    min_size = min(
                        [
                            unit.unitSize
                            for site in sites.values()
                            for building in site.buildings
                            for floor in building.floors
                            for unit in floor.units
                        ]
                    )
                    create_interactive_treemap(
                        sites, level, output_svg_file, width, height, min_size=min_size
                    )
            else:
                return "Invalid level", 400

        with open(output_svg_file, "r") as f:
            svg_content = f.read()

        cache[cache_key] = {"svg_content": svg_content, "filters": filters}

    return svg_content


@app.route("/clear_cache", methods=["GET"])
def clear_cache():
    filter_value = request.args.get("filter")
    keys_to_delete = [key for key in cache.keys() if filter_value in key]
    for key in keys_to_delete:
        del cache[key]
    return "Cache cleared", 200


@app.route("/get_filter_options", methods=["GET"])
def get_filter_options():
    """
    Fetches the options for the filters from the database and returns them as a JSON response to be used in the frontend.
    
    :return: options - A JSON response containing the options for the filters.
    """

    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        r"DBQ=" + database_file + ";"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    options = {
        "work_request_status": [],
        "requested_by": [],
        "craftsperson_name": [],
        "primary_trade": [],
    }

    try:
        # Fetch options for work_request_status
        cursor.execute("SELECT DISTINCT [Work Request Status] FROM Combined")
        options["work_request_status"] = [row[0] for row in cursor.fetchall()]

        # Fetch options for requested_by
        cursor.execute("SELECT DISTINCT [Requested by] FROM Combined")
        options["requested_by"] = [row[0] for row in cursor.fetchall()]

        # Fetch options for craftsperson_name
        cursor.execute("SELECT DISTINCT [Craftsperson Name] FROM Craftsperson")
        options["craftsperson_name"] = [row[0] for row in cursor.fetchall()]

        # Fetch options for primary_trade
        cursor.execute("SELECT DISTINCT [Primary Trade] FROM Craftsperson")
        options["primary_trade"] = [row[0] for row in cursor.fetchall()]

    except pyodbc.Error as e:
        error_message = f"Database query error: {str(e)}"
        print(error_message)
        return error_message, 500
    finally:
        conn.close()

    return jsonify(options)


@app.route("/get_unit_problems", methods=["GET"])
def get_unit_problems():
    """
    Fetches the problems for a specific unit based on the unit code and the specified filters and returns them as a JSON response to be used in the frontend.
    
    :return: problems - A JSON response containing the problems for the specified unit."""
    code = request.args.get("unit_code")

    work_request_status = request.args.get("work_request_status")
    craftsperson_name = request.args.get("craftsperson_name")
    primary_trade = request.args.get("primary_trade")

    print("Unit code: ", code)

    if not code:
        return "Unit code is required", 400
    
    site_code = ""
    if (len(code.split(":"))==4):
        site_code, building_code, floor_code, unit_code = code.split(":")
    elif (len(code.split(";"))==3):
        building_code, floor_code, unit_code = code.split(";")
    
    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        r"DBQ=" + database_file + ";"
    )

    try:
        conn = pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        error_message = f"Database connection error: {str(e)}"
        print(error_message)
        return error_message, 500

    query = """
    SELECT 
        Combined.[Activity Log ID], 
        Combined.[Work Description]
    FROM (Combined
    INNER JOIN Location ON Combined.LocationID = Location.LocationID)
    INNER JOIN Unit ON Location.UnitID = Unit.UnitID
    WHERE 1=1
    """

    if site_code != "":
        query+= f"AND Location.[Site Code] = '{site_code}' AND Location.[Building Code] = '{building_code}' AND Location.[Floor Code] = '{floor_code}' AND Unit.[Unit Code] = '{unit_code}'"
    else:
        query+= f"AND Location.[Building Code] = '{building_code}' AND Location.[Floor Code] = '{floor_code}' AND Unit.[Unit Code] = '{unit_code}'"

    if work_request_status != "":
        statuses = work_request_status.split(",")
        status_list = ", ".join([f"'{status.strip()}'" for status in statuses])
        query += f" AND Combined.[Work Request Status] IN ({status_list})"

    # Apply Craftsperson Name filter
    if craftsperson_name != "":
        names = craftsperson_name.split(",")
        name_list = ", ".join([f"'{name.strip()}'" for name in names])
        query += f" AND Craftsperson.[Craftsperson Name] IN ({name_list})"

    # Apply Primary Trade filter
    if primary_trade != "":
        trades = primary_trade.split(",")
        trade_list = ", ".join([f"'{trade.strip()}'" for trade in trades])
        query += f" AND Craftsperson.[Primary Trade] IN ({trade_list})"

    try:
        print("Executing ", query)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        problems = [{"log_id": row[0], "description": row[1]} for row in rows]
        return jsonify(problems)
    except pyodbc.Error as e:
        error_message = f"Database query error: {str(e)}"
        print(error_message)
        return error_message, 500
    except Exception as e:
        error_message = f"General error: {str(e)}"
        print(error_message)
        return error_message, 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)