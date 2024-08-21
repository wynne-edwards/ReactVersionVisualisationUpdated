from server import extract_data_from_access, generate_treemap_data, get_postgres_connection
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from server import generate_treemap_data, create_interactive_treemap, generate_color_scale, calculate_unit_size
import requests

# Sample data to simulate the expected structure of the DataFrame

sample_data = {
    "SiteCode": ["S1", "S1", "S1", "S2", "S2", "S3"],
    "SiteName": ["Site 1", "Site 1", "Site 1", "Site 2", "Site 2", "Site 3"],
    "Building Code": ["B1", "B1", "B2", "B1", "B2", "B1"],
    "Building Name": ["Building 1", "Building 1", "Building 2", "Building 1", "Building 2", "Building 1"],
    "Floor Code": ["F1", "F2", "F1", "F1", "F2", "F1"],
    "Floor Name": ["Floor 1", "Floor 2", "Floor 1", "Floor 1", "Floor 2", "Floor 1"],
    "Unit Code": ["U1", "U2", "U1", "U2", "U1", "U2"],
    "Unit Name": ["Unit 1", "Unit 2", "Unit 1", "Unit 2", "Unit 1", "Unit 2"],
    "IssueCount": [10, 20, 15, 25, 30, 5]
}

# Convert the sample data to a DataFrame
df = pd.DataFrame(sample_data)

# Define dimensions for the SVG
width = 800
height = 600
output_file = "output_treemap.svg"

# Print confirmation
print(f"Treemap generated and saved to {output_file}")

@profile
def test_performance():
    filters = {
        'work_request_status': 'Closed'
        # Add other filters as needed
    }
    conn = get_postgres_connection()
    df = extract_data_from_access(filters)
    print("DataFrame extracted:")
    print(df)

    # Generate treemap data
    sites = generate_treemap_data(df)
    generate_color_scale(df)
    create_interactive_treemap(sites, level="site", output_file=output_file, width=width, height=height)

@profile
def trigger_svg_generation():
    url = "http://127.0.0.1:5001/generate_svg"
    params = {
        "level": "site",
        "visualization_type": "squarified",
        "width": "800",
        "height": "600",
        "work_request_status": "Closed",
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        print("SVG generation successful")
        print(response.text)
    else:
        print(f"Failed to generate SVG: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_performance()
    trigger_svg_generation()
