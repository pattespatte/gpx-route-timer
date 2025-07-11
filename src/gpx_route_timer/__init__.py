#!/usr/bin/env python3
"""GPX Route Timer - Add timestamps to GPX files for multi-day hikes"""

__version__ = "0.1.0"

import sys
import subprocess
import os


def print_help():
    print(
        """
GPX Route Timer - Add timestamps to GPX files for multi-day hikes

Usage:
    python {script} [GPX_FILE_OR_URL] [options]

Features:
  - Calculate total route distance and suggest overnight stops.
  - Output a GPX file with timestamps.
  - Generate a Markdown itinerary with daily breakdowns and map links.
  - Generate a KML file for Google Earth visualization.
  - Detect existing overnight stops based on time gaps in the GPX.
  - Interactively set or adjust start/end times and overnight locations.
  - Validate route for realistic daily distances.
  - Download or load a GPX file from a URL or local path.
  - Handles missing dependencies automatically.

Options:
  [GPX_FILE_OR_URL]  The path or URL of the GPX file to process.
  -h, --help    Show this help message and exit.

For more information, see: https://github.com/pattespatte/gpx-route-timer
""".format(
            script=os.path.basename(sys.argv[0])
        )
    )


if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help"):
    print_help()
    sys.exit(0)

# Constants

# Default walking speed in kilometers per hour
WALKING_SPEED_KMH = 4.0

# Default start hour for each hiking day (9 AM)
DEFAULT_START_HOUR = 9

# Default end hour for the last hiking day (8 PM)
DEFAULT_END_HOUR = 20

# Default number of hiking days if not specified
DEFAULT_HIKING_DAYS = 4

# Time gap (in hours) used to detect overnight stops in GPX timestamps
OVERNIGHT_GAP_HOURS = 6

# Maximum number of days ahead allowed for Komoot GPX uploads
KOMOOT_MAX_DAYS_AHEAD = 14

GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"

GITHUB_URL = "https://github.com/pattespatte/gpx-route-timer"


def try_install_package(package):
    """Try to install a package using pip"""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except:
        return False


def check_and_install_dependencies():
    """Check for required packages and try to install if missing"""
    required = {
        "requests": "requests",
        "geopy": "geopy",
        "numpy": "numpy",
        "colorama": "colorama",
        "matplotlib": "matplotlib",
    }

    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            print(f"Package '{package}' not found. Attempting to install...")
            if try_install_package(package):
                print(f"✓ Successfully installed {package}")
                try:
                    __import__(module)
                except ImportError:
                    missing.append(package)
            else:
                missing.append(package)

    if missing:
        print("\n❌ Could not automatically install the following packages:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\nPlease install them manually using:")
        print(f"   pip install {' '.join(missing)}")
        sys.exit(1)


# Check dependencies before proceeding
check_and_install_dependencies()

# Now we can safely import everything
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from geopy.distance import geodesic
import numpy as np
import os
from urllib.parse import quote, urlparse
from colorama import Fore, Back, Style, init

# Initialize colorama
init(autoreset=True)


# Color constants for different message types
class Colors:
    SUCCESS = Fore.GREEN
    WARNING = Fore.YELLOW
    ERROR = Fore.RED
    INFO = Fore.CYAN
    HIGHLIGHT = Fore.MAGENTA
    PROMPT = Fore.BLUE + Style.BRIGHT  # For user input prompts
    BOLD = Style.BRIGHT
    RESET = Style.RESET_ALL

def get_user_input(prompt, default):
    """Get user input with a default value"""
    user_input = input(f"{prompt} [default: {default}]: ").strip()
    return user_input if user_input else default


def format_map_link(lat, lon):
    """Create a Google Maps link for coordinates"""
    return f"https://www.google.com/maps?q={lat},{lon}"


def format_route_link(all_points, sleep_stops):
    """Create a Google Maps route link for the entire route with waypoints and walking mode"""
    # Start point
    start_lat, start_lon = all_points[0]["coords"]

    # End point
    end_lat, end_lon = all_points[-1]["coords"]

    # Build the URL using Google Maps Directions API format
    base_url = "https://www.google.com/maps/dir/?api=1"

    # Add origin and destination
    url_params = [
        f"origin={start_lat},{start_lon}",
        f"destination={end_lat},{end_lon}",
        "travelmode=walking",
    ]

    # Add waypoints if there are sleep stops
    if sleep_stops:
        waypoints = []
        for stop in sleep_stops:
            lat, lon = stop["point"]["coords"]
            waypoints.append(f"{lat},{lon}")

        if waypoints:
            # Google Maps API allows up to 25 waypoints, but for better performance
            # and URL length limits, we'll limit to the first 8 waypoints
            if len(waypoints) > 8:
                waypoints = waypoints[:8]
                print(
                    f"Note: Limited to first 8 waypoints in Google Maps link due to URL length restrictions"
                )

            waypoints_str = "|".join(waypoints)
            url_params.append(f"waypoints={waypoints_str}")

    # Combine all parameters
    full_url = base_url + "&" + "&".join(url_params)

    return full_url


def find_closest_point(points, target_distance):
    """Find the point closest to a target cumulative distance"""
    closest_point = None
    min_diff = float("inf")

    for point in points:
        diff = abs(point["cumulative_distance"] - target_distance)
        if diff < min_diff:
            min_diff = diff
            closest_point = point

    return closest_point


def safe_geodesic(point1, point2):
    """Calculate geodesic distance with error handling"""
    try:
        return geodesic(point1, point2).km
    except Exception as e:
        # Fallback to simple Euclidean approximation
        lat_diff = point2[0] - point1[0]
        lon_diff = point2[1] - point1[1]
        return ((lat_diff**2 + lon_diff**2) ** 0.5) * 111  # Rough km conversion


def calculate_distances_vectorized(points):
    """Calculate distances using vectorized operations with numpy"""
    if len(points) < 2:
        return np.array([0.0])

    # Extract coordinates as numpy array
    coords = np.array([point["coords"] for point in points])

    # Calculate differences between consecutive points
    lat_diff = np.diff(coords[:, 0])
    lon_diff = np.diff(coords[:, 1])

    # More accurate distance calculation using Haversine-like approximation
    # Convert to radians
    lat_rad = np.radians(coords[:-1, 0])
    lat_diff_rad = np.radians(lat_diff)
    lon_diff_rad = np.radians(lon_diff)

    # Haversine formula approximation
    # For small distances, this is quite accurate
    a = (
        np.sin(lat_diff_rad / 2) ** 2
        + np.cos(lat_rad)
        * np.cos(lat_rad + lat_diff_rad)
        * np.sin(lon_diff_rad / 2) ** 2
    )
    distances = 2 * 6371 * np.arcsin(np.sqrt(a))  # Earth radius = 6371 km

    # Return cumulative distances
    return np.concatenate(([0], np.cumsum(distances)))


def calculate_distances_fallback(points):
    """Fallback distance calculation using geopy for accuracy"""
    distances = [0.0]
    total_distance = 0.0

    for i in range(1, len(points)):
        dist = safe_geodesic(points[i - 1]["coords"], points[i]["coords"])
        total_distance += dist
        distances.append(total_distance)

    return np.array(distances)


def calculate_cumulative_distances(all_points):
    """Calculate cumulative distances with vectorized operations when possible"""
    num_points = len(all_points)

    print(f"\n{Colors.INFO}Calculating route distance...")

    # For small files or when high accuracy is needed, use geopy
    # For large files, use vectorized calculation for speed
    use_vectorized = num_points > 1000

    try:
        if use_vectorized:
            print(f"{Colors.INFO}Using fast vectorized calculation for large GPX file...")
            distances = calculate_distances_vectorized(all_points)
        else:
            print(f"{Colors.INFO}Using high-accuracy calculation...")
            distances = calculate_distances_fallback(all_points)

        # Assign distances to points
        for i, point in enumerate(all_points):
            point["cumulative_distance"] = distances[i]

        total_distance = distances[-1]

        if use_vectorized:
            print(f"{Colors.SUCCESS}Fast calculation completed for {num_points} points")
        else:
            print(f"{Colors.SUCCESS}High-accuracy calculation completed for {num_points} points")

    except Exception as e:
        print(f"{Colors.ERROR}Error in vectorized calculation, falling back to point-by-point: {e}")
        # Fallback to original method
        total_distance = 0

        for i in range(num_points):
            if i > 0:
                dist = safe_geodesic(
                    all_points[i - 1]["coords"], all_points[i]["coords"]
                )
                total_distance += dist
            all_points[i]["cumulative_distance"] = total_distance

            # Show progress for large files
            if num_points > 1000 and i % 100 == 0:
                progress = (i / num_points) * 100
                print(f"\r{Colors.INFO}Progress: {Colors.HIGHLIGHT}{progress:.1f}%{Colors.RESET} ({i}/{num_points} points)", end="")

        if num_points > 1000:
            print(f"\r{Colors.SUCCESS}Progress: 100.0% ({num_points}/{num_points} points) - Done!")

    return total_distance


def display_sleep_stops(sleep_stops, total_distance, title="Sleep-over locations:"):
    """Display sleep stops in a consistent format"""
    print(f"\n{Colors.HIGHLIGHT}{title}")
    for i, stop in enumerate(sleep_stops):
        lat, lon = stop["point"]["coords"]
        actual_dist = stop["point"]["cumulative_distance"]

        # Calculate today's distance
        if i == 0:
            today_distance = actual_dist
        else:
            today_distance = (
                actual_dist - sleep_stops[i - 1]["point"]["cumulative_distance"]
            )

        # Calculate remaining distance
        remaining_distance = total_distance - actual_dist

        print(f"\n{Colors.BOLD}Night {stop['night']}:")
        print(
            f"  Distance from today's start: {Colors.SUCCESS}{today_distance:.2f} km{Colors.RESET} (distance to end: {remaining_distance:.2f} km)"
        )
        print(f"  Coordinates: {Colors.INFO}{lat:.6f}, {lon:.6f}")
        print(f"  View on map: {Colors.INFO}{format_map_link(lat, lon)}")


def parse_coordinates(coord_string):
    """Parse coordinates in various formats"""
    coord_string = coord_string.strip()

    # Try different separators
    for separator in [",", " ", ";", "\t"]:
        if separator in coord_string:
            parts = coord_string.split(separator)
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    # Validate coordinate ranges
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return lat, lon
                except ValueError:
                    continue

    raise ValueError(
        "Could not parse coordinates. Use format: lat,lon (e.g., 56.123,12.456)"
    )


def load_gpx_content(source):
    """Load GPX content from either a URL or local file path"""
    # Check if it's a URL
    parsed = urlparse(source)
    is_url = parsed.scheme in ("http", "https")

    if is_url:
        print(f"\n{Colors.INFO}Downloading GPX file from URL...")
        try:
            response = requests.get(source)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"{Colors.ERROR}Error downloading file: {e}")
            sys.exit(1)
    else:
        # Treat as local file path
        print(f"\n{Colors.INFO}Loading GPX file from local path...")
        try:
            # Expand user home directory if needed
            file_path = os.path.expanduser(source)
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"{Colors.ERROR}Error: File not found: {file_path}")
            sys.exit(1)
        except Exception as e:
            print(f"{Colors.ERROR}Error reading file: {e}")
            sys.exit(1)


def detect_gpx_type(root):
    """Detect the type of GPX content and return waypoints, tracks, or routes"""
    waypoints = root.findall(f".//{{{GPX_NAMESPACE}}}wpt")
    tracks = root.findall(f".//{{{GPX_NAMESPACE}}}trk")
    routes = root.findall(f".//{{{GPX_NAMESPACE}}}rte")

    # Return in order of preference: routes, tracks, waypoints
    if routes:
        return "route", routes
    elif tracks:
        return "track", tracks
    elif waypoints:
        return "waypoint", waypoints
    else:
        return "none", []


def extract_points_from_waypoints(waypoints):
    """Convert waypoints to track-like points"""
    all_points = []
    for wpt in waypoints:
        lat = float(wpt.get("lat"))
        lon = float(wpt.get("lon"))
        all_points.append(
            {"element": wpt, "coords": (lat, lon), "cumulative_distance": 0}
        )
    return all_points


def extract_points_from_routes(routes):
    """Extract points from route elements"""
    all_points = []
    for rte in routes:
        for pt in rte.findall(f".//{{{GPX_NAMESPACE}}}rtept"):
            lat = float(pt.get("lat"))
            lon = float(pt.get("lon"))
            all_points.append(
                {"element": pt, "coords": (lat, lon), "cumulative_distance": 0}
            )
    return all_points


def extract_points_from_tracks(tracks):
    """Extract points from track elements"""
    all_points = []
    for trk in tracks:
        for seg in trk.findall(f".//{{{GPX_NAMESPACE}}}trkseg"):
            for pt in seg.findall(f".//{{{GPX_NAMESPACE}}}trkpt"):
                lat = float(pt.get("lat"))
                lon = float(pt.get("lon"))
                all_points.append(
                    {"element": pt, "coords": (lat, lon), "cumulative_distance": 0}
                )
    return all_points


def create_komoot_compatible_gpx(
    all_points, sleep_stops, start_time, end_time, walking_speed, route_name
):
    """Create a new GPX structure with routes that matches Komoot's expected format"""
    # Create root element with proper attributes
    root = ET.Element("gpx")
    root.set("version", "1.1")
    root.set("creator", GITHUB_URL)
    root.set("xmlns", GPX_NAMESPACE)
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set(
        "xsi:schemaLocation",
        f"{GPX_NAMESPACE} {GPX_NAMESPACE}/gpx.xsd",
    )

    # Add metadata
    metadata = ET.SubElement(root, "metadata")
    name = ET.SubElement(metadata, "name")
    name.text = route_name

    author = ET.SubElement(metadata, "author")
    link = ET.SubElement(author, "link")
    link.set("href", GITHUB_URL)
    link_text = ET.SubElement(link, "text")
    link_text.text = "GPX Route Timer"
    link_type = ET.SubElement(link, "type")
    link_type.text = "text/html"

    # Add creation time
    time_elem = ET.SubElement(metadata, "time")
    time_elem.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Add route (instead of track)
    rte = ET.SubElement(root, "rte")
    rte_name = ET.SubElement(rte, "name")
    rte_name.text = route_name

    # Calculate actual walking schedule and add route points
    current_day = 0
    day_start_time = start_time
    day_distance_walked = 0

    # Calculate total days
    total_days = len(sleep_stops) + 1 if sleep_stops else 1

    for i, point in enumerate(all_points):
        # Check if we've reached a sleep stop
        for stop in sleep_stops:
            if i > 0 and stop["point"] == point:
                # Start new day
                current_day += 1
                # For middle days, always start at 9:00
                if current_day < total_days - 1:
                    day_start_time = start_time.replace(
                        hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0
                    ) + timedelta(days=current_day)
                else:
                    # Last day - calculate start time based on end time and remaining distance
                    remaining_distance = (
                        all_points[-1]["cumulative_distance"]
                        - point["cumulative_distance"]
                    )
                    hours_needed = remaining_distance / walking_speed
                    day_start_time = end_time - timedelta(hours=hours_needed)
                    day_start_time = day_start_time.replace(microsecond=0)

                day_distance_walked = point["cumulative_distance"]

        # Calculate time for this point
        distance_today = point["cumulative_distance"] - day_distance_walked
        hours_today = distance_today / walking_speed
        current_time = day_start_time + timedelta(hours=hours_today)

        # Create route point (rtept instead of trkpt)
        rtept = ET.SubElement(rte, "rtept")
        rtept.set("lat", str(point["coords"][0]))
        rtept.set("lon", str(point["coords"][1]))

        # Add elevation if it exists
        ele_elem = point["element"].find(".//ele")
        if ele_elem is None:
            ele_elem = point["element"].find(f".//{{{GPX_NAMESPACE}}}ele")
        if ele_elem is not None:
            ele = ET.SubElement(rtept, "ele")
            ele.text = ele_elem.text

        # Add time with exactly 3 decimal places for milliseconds
        time_elem = ET.SubElement(rtept, "time")
        # Format: YYYY-MM-DDTHH:MM:SS.sssZ
        time_elem.text = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    return root


def create_daily_gpx_files(
    all_points,
    sleep_stops,
    start_time,
    end_time,
    walking_speed,
    route_name,
    base_filename,
):
    """Create separate GPX files for each hiking day"""
    daily_files = []

    # Calculate total days
    total_days = len(sleep_stops) + 1 if sleep_stops else 1

    # Create day boundaries (point indices where each day starts/ends)
    day_boundaries = [0]  # Start with first point

    # Add sleep stop indices as day boundaries
    for stop in sleep_stops:
        for i, point in enumerate(all_points):
            if point == stop["point"]:
                day_boundaries.append(i)
                break

    # Add last point as final boundary
    day_boundaries.append(len(all_points) - 1)

    # Create GPX file for each day
    for day_num in range(total_days):
        start_idx = day_boundaries[day_num]
        end_idx = day_boundaries[day_num + 1]

        # Get points for this day
        day_points = all_points[start_idx : end_idx + 1]

        # Calculate day start and end times
        if day_num == 0:
            # First day
            day_start_time = start_time
        else:
            # Middle days start at 9:00
            day_start_time = start_time.replace(
                hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0
            ) + timedelta(days=day_num)

        if day_num == total_days - 1:
            # Last day
            day_end_time = end_time
        else:
            # Calculate end time based on distance and walking speed
            day_distance = (
                day_points[-1]["cumulative_distance"]
                - day_points[0]["cumulative_distance"]
            )
            day_hours = day_distance / walking_speed
            day_end_time = day_start_time + timedelta(hours=day_hours)

        # Create day-specific route name
        day_route_name = f"{route_name} - Day {day_num + 1}"

        # Create GPX structure for this day
        root = ET.Element("gpx")
        root.set("version", "1.1")
        root.set("creator", GITHUB_URL)
        root.set("xmlns", GPX_NAMESPACE)
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set(
            "xsi:schemaLocation",
            f"{GPX_NAMESPACE} {GPX_NAMESPACE}/gpx.xsd",
        )

        # Add metadata
        metadata = ET.SubElement(root, "metadata")
        name = ET.SubElement(metadata, "name")
        name.text = day_route_name

        author = ET.SubElement(metadata, "author")
        link = ET.SubElement(author, "link")
        link.set("href", GITHUB_URL)
        link_text = ET.SubElement(link, "text")
        link_text.text = "GPX Route Timer"
        link_type = ET.SubElement(link, "type")
        link_type.text = "text/html"

        # Add creation time
        time_elem = ET.SubElement(metadata, "time")
        time_elem.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Add route
        rte = ET.SubElement(root, "rte")
        rte_name = ET.SubElement(rte, "name")
        rte_name.text = day_route_name

        # Add route points with timestamps
        day_distance_start = day_points[0]["cumulative_distance"]

        for point in day_points:
            # Calculate time for this point within the day
            distance_from_day_start = point["cumulative_distance"] - day_distance_start
            hours_from_day_start = distance_from_day_start / walking_speed
            current_time = day_start_time + timedelta(hours=hours_from_day_start)

            # Create route point
            rtept = ET.SubElement(rte, "rtept")
            rtept.set("lat", str(point["coords"][0]))
            rtept.set("lon", str(point["coords"][1]))

            # Add elevation if it exists
            ele_elem = point["element"].find(".//ele")
            if ele_elem is None:
                ele_elem = point["element"].find(f".//{{{GPX_NAMESPACE}}}ele")
            if ele_elem is not None:
                ele = ET.SubElement(rtept, "ele")
                ele.text = ele_elem.text

            # Add time
            time_elem = ET.SubElement(rtept, "time")
            time_elem.text = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        # Pretty print the XML
        indent_xml(root)

        # Generate filename for this day
        day_filename = f"{base_filename}--day-{day_num + 1:02d}.gpx"

        # Save the day's GPX file
        tree = ET.ElementTree(root)
        tree.write(day_filename, xml_declaration=True, encoding="UTF-8", method="xml")

        daily_files.append(
            {
                "filename": day_filename,
                "day": day_num + 1,
                "start_time": day_start_time,
                "end_time": day_end_time,
                "distance": day_points[-1]["cumulative_distance"]
                - day_points[0]["cumulative_distance"],
                "points": len(day_points),
            }
        )

    return daily_files


def indent_xml(elem, level=0):
    """Add pretty printing to XML"""
    i = "\n" + level * "\t"
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "\t"
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def save_markdown_itinerary(
    filename,
    start_time,
    end_time,
    total_distance,
    sleep_stops,
    walking_speed,
    all_points,
):
    """Save the itinerary as a markdown file"""
    md_content = []
    md_content.append(f"# Hiking Itinerary\n")
    md_content.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    md_content.append(f"## Overview\n")
    md_content.append(f"- **Total Distance:** {total_distance:.2f} km")
    md_content.append(f"- **Start:** {start_time.strftime('%Y-%m-%d %H:%M')}")
    md_content.append(f"- **End:** {end_time.strftime('%Y-%m-%d %H:%M')}")
    md_content.append(f"- **Walking Speed:** {walking_speed} km/h")
    md_content.append(
        f"- **Total Days:** {(end_time.date() - start_time.date()).days + 1}"
    )
    md_content.append(f"- **Nights:** {len(sleep_stops)}\n")

    md_content.append(f"## Daily Schedule\n")

    # Calculate total days
    total_days = len(sleep_stops) + 1 if sleep_stops else 1

    # Day 1
    md_content.append(f"### Day 1 - {start_time.strftime('%A, %B %d, %Y')}")
    md_content.append(f"- **Start:** {start_time.strftime('%H:%M')}")
    if sleep_stops:
        day1_distance = sleep_stops[0]["point"]["cumulative_distance"]
        day1_hours = day1_distance / walking_speed
        md_content.append(f"- **Distance:** {day1_distance:.2f} km")
        md_content.append(
            f"- **Walking Time:** {day1_hours:.1f} hours ({int(day1_hours * 60)} minutes)"
        )
        md_content.append(
            f"- **End:** Overnight at [{sleep_stops[0]['point']['coords'][0]:.6f}, {sleep_stops[0]['point']['coords'][1]:.6f}]({format_map_link(sleep_stops[0]['point']['coords'][0], sleep_stops[0]['point']['coords'][1])})\n"
        )
    else:
        md_content.append(f"- **Distance:** {total_distance:.2f} km")
        md_content.append(
            f"- **Walking Time:** {total_distance/walking_speed:.1f} hours"
        )
        md_content.append(f"- **End:** {end_time.strftime('%H:%M')}\n")

    # Middle days
    for i in range(len(sleep_stops)):
        if i == 0:
            continue  # Skip first night as it's covered in Day 1

        day_num = i + 1
        day_date = start_time + timedelta(days=day_num - 1)

        # Determine start time for this day
        if day_num < total_days:
            # Middle days always start at 9:00
            day_start_time = day_date.replace(hour=DEFAULT_START_HOUR, minute=0)
        else:
            # Last day - calculate start time based on end time and remaining distance
            remaining_distance = (
                total_distance - sleep_stops[i - 1]["point"]["cumulative_distance"]
            )
            hours_needed = remaining_distance / walking_speed
            day_start_time = end_time - timedelta(hours=hours_needed)

        md_content.append(f"### Day {day_num} - {day_date.strftime('%A, %B %d, %Y')}")
        md_content.append(f"- **Start:** {day_start_time.strftime('%H:%M')}")

        prev_distance = sleep_stops[i - 1]["point"]["cumulative_distance"]
        day_distance = sleep_stops[i]["point"]["cumulative_distance"] - prev_distance
        day_hours = day_distance / walking_speed

        md_content.append(f"- **Distance:** {day_distance:.2f} km")
        md_content.append(
            f"- **Walking Time:** {day_hours:.1f} hours ({int(day_hours * 60)} minutes)"
        )
        md_content.append(
            f"- **End:** Overnight at [{sleep_stops[i]['point']['coords'][0]:.6f}, {sleep_stops[i]['point']['coords'][1]:.6f}]({format_map_link(sleep_stops[i]['point']['coords'][0], sleep_stops[i]['point']['coords'][1])})\n"
        )

    # Last day (if there are sleep stops)
    if sleep_stops:
        last_day = len(sleep_stops) + 1
        last_date = start_time + timedelta(days=last_day - 1)

        # Calculate start time for last day based on end time
        last_distance = total_distance - sleep_stops[-1]["point"]["cumulative_distance"]
        last_hours = last_distance / walking_speed
        last_day_start = end_time - timedelta(hours=last_hours)

        md_content.append(f"### Day {last_day} - {last_date.strftime('%A, %B %d, %Y')}")
        md_content.append(f"- **Start:** {last_day_start.strftime('%H:%M')}")
        md_content.append(f"- **Distance:** {last_distance:.2f} km")
        md_content.append(
            f"- **Walking Time:** {last_hours:.1f} hours ({int(last_hours * 60)} minutes)"
        )
        md_content.append(f"- **End:** {end_time.strftime('%H:%M')} - Finish!\n")

    md_content.append(f"## Map Links\n")
    md_content.append(
        f"- [Start Point]({format_map_link(all_points[0]['coords'][0], all_points[0]['coords'][1])})"
    )
    for i, stop in enumerate(sleep_stops):
        md_content.append(
            f"- [Night {i+1} Camp]({format_map_link(stop['point']['coords'][0], stop['point']['coords'][1])})"
        )
    md_content.append(
        f"- [End Point]({format_map_link(all_points[-1]['coords'][0], all_points[-1]['coords'][1])})"
    )
    md_content.append(
        f"- [Entire route on Google Maps]({format_route_link(all_points, sleep_stops)})"
    )

    md_content.append(f"\n## 3D Visualization\n")
    md_content.append(f"To view this route in 3D:")
    md_content.append(
        f"- **Google Earth Web**: Go to [earth.google.com](https://earth.google.com/web/), click the menu (☰), select 'Projects' → 'Import KML file', and upload the `.kml` file"
    )
    md_content.append(
        f"- **Google Earth Desktop**: Double-click the `.kml` file (requires Google Earth to be installed)"
    )
    md_content.append(
        f"- **Mobile**: Import the `.kml` file through the Google Earth mobile app"
    )
    # Add image if it exists
    image_filename = os.path.splitext(filename)[0] + ".png"
    md_content.append(f"![Route map]({os.path.basename(image_filename)})\n")

    # Write to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))

    print(f"{Colors.SUCCESS}Markdown file saved as '{filename}'")


def save_kml_file(filename, all_points, sleep_stops, route_name, start_time, end_time):
    """Save the route as a KML file"""
    kml_content = []
    kml_content.append('<?xml version="1.0" encoding="UTF-8"?>')
    kml_content.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
    kml_content.append("  <Document>")
    kml_content.append(f"    <name>{route_name}</name>")
    kml_content.append(
        f'    <description>Hiking route from {start_time.strftime("%Y-%m-%d")} to {end_time.strftime("%Y-%m-%d")}</description>'
    )

    # Add styles
    kml_content.append('    <Style id="routeStyle">')
    kml_content.append("      <LineStyle>")
    kml_content.append("        <color>ff0000ff</color>")  # Red line
    kml_content.append("        <width>3</width>")
    kml_content.append("      </LineStyle>")
    kml_content.append("    </Style>")

    kml_content.append('    <Style id="startStyle">')
    kml_content.append("      <IconStyle>")
    kml_content.append("        <color>ff00ff00</color>")  # Green
    kml_content.append("        <scale>1.2</scale>")
    kml_content.append("      </IconStyle>")
    kml_content.append("    </Style>")

    kml_content.append('    <Style id="sleepStyle">')
    kml_content.append("      <IconStyle>")
    kml_content.append("        <color>ff0000ff</color>")  # Red
    kml_content.append("        <scale>1.1</scale>")
    kml_content.append("      </IconStyle>")
    kml_content.append("    </Style>")

    kml_content.append('    <Style id="endStyle">')
    kml_content.append("      <IconStyle>")
    kml_content.append("        <color>ffff0000</color>")  # Blue
    kml_content.append("        <scale>1.2</scale>")
    kml_content.append("      </IconStyle>")
    kml_content.append("    </Style>")

    # Add route line
    kml_content.append("    <Placemark>")
    kml_content.append(f"      <name>{route_name} - Track</name>")
    kml_content.append("      <styleUrl>#routeStyle</styleUrl>")
    kml_content.append("      <LineString>")
    kml_content.append("        <tessellate>1</tessellate>")
    kml_content.append("        <coordinates>")

    # Add all track points
    for point in all_points:
        lat, lon = point["coords"]
        # KML uses lon,lat,elevation format
        kml_content.append(f"          {lon},{lat},0")

    kml_content.append("        </coordinates>")
    kml_content.append("      </LineString>")
    kml_content.append("    </Placemark>")

    # Add start point
    start_lat, start_lon = all_points[0]["coords"]
    kml_content.append("    <Placemark>")
    kml_content.append("      <name>Start</name>")
    kml_content.append(
        f'      <description>Start of hike: {start_time.strftime("%Y-%m-%d %H:%M")}</description>'
    )
    kml_content.append("      <styleUrl>#startStyle</styleUrl>")
    kml_content.append("      <Point>")
    kml_content.append(f"        <coordinates>{start_lon},{start_lat},0</coordinates>")
    kml_content.append("      </Point>")
    kml_content.append("    </Placemark>")

    # Add sleep stops
    for i, stop in enumerate(sleep_stops):
        lat, lon = stop["point"]["coords"]
        kml_content.append("    <Placemark>")
        kml_content.append(f"      <name>Night {i+1} Camp</name>")
        kml_content.append(
            f'      <description>Overnight stop {i+1}<br/>Distance: {stop["point"]["cumulative_distance"]:.2f} km</description>'
        )
        kml_content.append("      <styleUrl>#sleepStyle</styleUrl>")
        kml_content.append("      <Point>")
        kml_content.append(f"        <coordinates>{lon},{lat},0</coordinates>")
        kml_content.append("      </Point>")
        kml_content.append("    </Placemark>")

    # Add end point
    end_lat, end_lon = all_points[-1]["coords"]
    kml_content.append("    <Placemark>")
    kml_content.append("      <name>Finish</name>")
    kml_content.append(
        f'      <description>End of hike: {end_time.strftime("%Y-%m-%d %H:%M")}</description>'
    )
    kml_content.append("      <styleUrl>#endStyle</styleUrl>")
    kml_content.append("      <Point>")
    kml_content.append(f"        <coordinates>{end_lon},{end_lat},0</coordinates>")
    kml_content.append("      </Point>")
    kml_content.append("    </Placemark>")

    kml_content.append("  </Document>")
    kml_content.append("</kml>")

    # Write to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(kml_content))

    print(f"{Colors.SUCCESS}KML file saved as '{filename}'")


def validate_gpx_data(all_points, sleep_stops, total_distance):
    """Validate GPX data and return list of warnings"""
    warnings = []
    
    # Check if route has reasonable number of points
    if len(all_points) < 2:
        warnings.append("Route has very few points (less than 2)")
    
    # Check for reasonable daily distances
    if sleep_stops:
        daily_distances = []
        prev_distance = 0
        
        for stop in sleep_stops:
            daily_distance = stop["point"]["cumulative_distance"] - prev_distance
            daily_distances.append(daily_distance)
            prev_distance = stop["point"]["cumulative_distance"]
        
        # Add final day distance
        final_distance = total_distance - prev_distance
        daily_distances.append(final_distance)
        
        # Check for unreasonably long daily distances (over 40km)
        for i, distance in enumerate(daily_distances):
            if distance > 40:
                warnings.append(f"Day {i+1} distance is very long: {distance:.1f} km")
            elif distance < 1:
                warnings.append(f"Day {i+1} distance is very short: {distance:.1f} km")
    
    # Check total distance reasonableness
    if total_distance > 500:
        warnings.append(f"Total distance is very long: {total_distance:.1f} km")
    elif total_distance < 1:
        warnings.append(f"Total distance is very short: {total_distance:.1f} km")
    
    # Check for duplicate coordinates (might indicate GPS errors)
    coord_counts = {}
    for point in all_points:
        coord_key = f"{point['coords'][0]:.6f},{point['coords'][1]:.6f}"
        coord_counts[coord_key] = coord_counts.get(coord_key, 0) + 1
    
    duplicate_coords = sum(1 for count in coord_counts.values() if count > 1)
    if duplicate_coords > len(all_points) * 0.1:  # More than 10% duplicates
        warnings.append(f"High number of duplicate coordinates detected: {duplicate_coords}")
    
    return warnings


def save_route_image(filename, all_points, sleep_stops, route_name):
    """Save a PNG image of the route using matplotlib"""
    import matplotlib.pyplot as plt

    lats = [pt["coords"][0] for pt in all_points]
    lons = [pt["coords"][1] for pt in all_points]

    plt.figure(figsize=(8, 6))
    plt.plot(lons, lats, color="blue", linewidth=2, label="Route")

    # Mark start and end
    plt.scatter(lons[0], lats[0], color="green", s=80, label="Start", zorder=5)
    plt.scatter(lons[-1], lats[-1], color="red", s=80, label="End", zorder=5)

    # Mark sleep stops
    if sleep_stops:
        sleep_lats = [stop["point"]["coords"][0] for stop in sleep_stops]
        sleep_lons = [stop["point"]["coords"][1] for stop in sleep_stops]
        plt.scatter(sleep_lons, sleep_lats, color="orange", s=60, label="Overnight", zorder=5)

    plt.title(route_name)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"{Colors.SUCCESS}PNG image saved as '{filename}'")


def main():
    # Support -e or -example for the example GPX
    example_url = (
        "https://github.com/pattespatte/gpx-route-timer/raw/main/misc/example.gpx"
    )
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("-h", "--help"):
            print_help()
            sys.exit(0)
        elif arg in ("-e", "-example"):
            source = example_url
            print(f"\n{Colors.INFO}Using example GPX source: {source}")
        else:
            source = arg
            print(f"\n{Colors.INFO}Using GPX source from command line: {source}")
    else:
        print(f"\n{Colors.INFO}GPX source can be either a URL (http://...) or a local file path")
        source = get_user_input("GPX source (URL or file path)", example_url)

    # Load GPX content
    gpx_xml = load_gpx_content(source)

    # Parse XML with proper namespace handling
    try:
        root = ET.fromstring(gpx_xml)
    except ET.ParseError as e:
        print(f"{Colors.ERROR}Error parsing GPX file: {e}")
        sys.exit(1)

    # Detect GPX type and extract points accordingly
    gpx_type, elements = detect_gpx_type(root)

    if gpx_type == "none":
        print(f"{Colors.ERROR}Error: No waypoints, tracks, or routes found in GPX file")
        sys.exit(1)

    # Handle different GPX types
    if gpx_type == "waypoint":
        print(f"{Colors.INFO}Found {len(elements)} waypoints in the GPX file.")
        print(f"{Colors.WARNING}The input GPX does not contain a route or track, only individual waypoints.")
        print(f"{Colors.INFO}These waypoints can be converted into a planned route by connecting them in order.")

        convert = input(f"{Colors.PROMPT}Convert waypoints to a route? (yes/no): {Colors.RESET}").strip().lower()
        if convert != "yes":
            print(f"{Colors.WARNING}Exiting without processing.")
            sys.exit(0)

        all_points = extract_points_from_waypoints(elements)
        print(f"{Colors.INFO}Converting {len(all_points)} waypoints to a planned route...")

    elif gpx_type == "track":
        print(f"{Colors.INFO}Found recorded track data in the GPX file.")
        print(f"{Colors.INFO}The input contains a recorded path (track). It will be converted into a planned route.")

        all_points = extract_points_from_tracks(elements)
        print(f"{Colors.INFO}Converting {len(all_points)} track points to a planned route...")

    elif gpx_type == "route":
        print(f"{Colors.INFO}Found route data in the GPX file.")
        all_points = extract_points_from_routes(elements)
        print(f"{Colors.INFO}Processing {len(all_points)} route points...")

    if not all_points:
        print(f"{Colors.ERROR}Error: No points could be extracted from the GPX file")
        sys.exit(1)

    # Calculate cumulative distance with progress indicator
    total_distance = calculate_cumulative_distances(all_points)

    # After calculating total distance, add Komoot notice
    print(f"\n{Colors.INFO}Total distance: {Colors.HIGHLIGHT}{total_distance:.2f} km")

    # ... existing code for detecting overnight stops ...

    # Add Komoot compatibility notice
    suggested_date = datetime.now() + timedelta(days=7)
    suggested_date = suggested_date.replace(
        hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0
    )
    print(
        f"\n{Colors.WARNING}Please note that Komoot will only accept a start time that is no longer than {KOMOOT_MAX_DAYS_AHEAD} days ahead. "
        f"You can use {Colors.HIGHLIGHT}{suggested_date.strftime('%Y-%m-%dT%H:%M')}{Colors.RESET} (7 days from now)\n"
    )

    # Check if the GPX already has timestamps
    existing_start_time = None
    existing_end_time = None

    # Find first and last timestamps in the GPX
    for pt in all_points[0]["element"].iter():
        if pt.tag == "time" or pt.tag.endswith("}time"):
            try:
                existing_start_time = datetime.fromisoformat(pt.text.rstrip("Z"))
                break
            except:
                pass

    for pt in all_points[-1]["element"].iter():
        if pt.tag == "time" or pt.tag.endswith("}time"):
            try:
                existing_end_time = datetime.fromisoformat(pt.text.rstrip("Z"))
                break
            except:
                pass

    # Handle start time
    if existing_start_time:
        print(f"\n{Colors.INFO}Start time: {Colors.HIGHLIGHT}{existing_start_time.strftime('%Y-%m-%dT%H:%M')}")
        print(f"{Colors.INFO}(To keep, press ENTER. To set a new date, use the format YYYY-MM-DDTHH:MM):")
        start_time_input = input().strip()

        if start_time_input:
            try:
                start_time = datetime.fromisoformat(start_time_input)
            except ValueError:
                print(f"{Colors.ERROR}Invalid date format. Please use YYYY-MM-DDTHH:MM")
                sys.exit(1)
        else:
            start_time = existing_start_time
    else:
        # No existing timestamp, use default
        default_start_date = datetime.now() + timedelta(days=7)
        default_start_date = default_start_date.replace(
            hour=DEFAULT_START_HOUR, minute=0, second=0, microsecond=0
        )
        default_start = default_start_date.strftime("%Y-%m-%dT%H:%M")

        start_time_str = get_user_input("Start time (YYYY-MM-DDTHH:MM)", default_start)
        try:
            start_time = datetime.fromisoformat(start_time_str)
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DDTHH:MM")
            sys.exit(1)

    # Handle end time
    if existing_end_time:
        print(f"\n{Colors.INFO}End time: {Colors.HIGHLIGHT}{existing_end_time.strftime('%Y-%m-%dT%H:%M')}")
        print(f"{Colors.INFO}(To keep, press ENTER. To set a new date, use the format YYYY-MM-DDTHH:MM):")
        end_time_input = input().strip()

        if end_time_input:
            try:
                end_time = datetime.fromisoformat(end_time_input)
            except ValueError:
                print(f"{Colors.ERROR}Invalid date format. Please use YYYY-MM-DDTHH:MM")
                sys.exit(1)
        else:
            end_time = existing_end_time
    else:
        # No existing timestamp, calculate default based on start time
        default_end_date = start_time + timedelta(days=DEFAULT_HIKING_DAYS)
        default_end_date = default_end_date.replace(
            hour=DEFAULT_END_HOUR, minute=0, second=0, microsecond=0
        )
        default_end = default_end_date.strftime("%Y-%m-%dT%H:%M")

        end_time_str = get_user_input("End time (YYYY-MM-DDTHH:MM)", default_end)
        try:
            end_time = datetime.fromisoformat(end_time_str)
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DDTHH:MM")
            sys.exit(1)

    # Add a friendly warning if dates are still too far ahead
    days_ahead = (start_time - datetime.now()).days
    if days_ahead > KOMOOT_MAX_DAYS_AHEAD:
        print(f"\n{Colors.WARNING}⚠️  Note: Start date is {days_ahead} days in the future.")
        print(
            f"   Some services like Komoot may reject GPX files with dates more than {KOMOOT_MAX_DAYS_AHEAD} days ahead."
        )

    # Calculate hiking parameters
    total_hours = (end_time - start_time).total_seconds() / 3600
    walking_speed = WALKING_SPEED_KMH
    walking_hours_needed = total_distance / walking_speed

    print(f"\n{Colors.INFO}Total time available: {Colors.HIGHLIGHT}{total_hours:.1f} hours")
    print(
        f"{Colors.INFO}Walking time needed at {walking_speed} km/h: {Colors.HIGHLIGHT}{walking_hours_needed:.1f} hours"
    )

    if walking_hours_needed > total_hours:
        print(f"\n{Colors.ERROR}Warning: Not enough time to complete the hike at the specified speed!")
        return

    # Calculate number of days and nights (needed for both existing and new overnight stops)
    num_days = (end_time.date() - start_time.date()).days + 1
    num_nights = num_days - 1

    # Detect existing overnight stops based on time gaps in timestamps
    existing_stop_indices = []
    if all_points and len(all_points) > 1:
        # Check if GPX has timestamps and look for gaps indicating overnight stops
        timestamps = []
        for i, point in enumerate(all_points):
            time_elem = None
            # Look for time element in the point
            for elem in point["element"].iter():
                if elem.tag == "time" or elem.tag.endswith("}time"):
                    time_elem = elem
                    break
            
            if time_elem is not None and time_elem.text:
                try:
                    timestamp = datetime.fromisoformat(time_elem.text.rstrip("Z"))
                    timestamps.append((i, timestamp))
                except:
                    pass
        
        # Look for gaps of more than OVERNIGHT_GAP_HOURS hours
        if len(timestamps) > 1:
            for i in range(1, len(timestamps)):
                prev_idx, prev_time = timestamps[i-1]
                curr_idx, curr_time = timestamps[i]
                time_gap = (curr_time - prev_time).total_seconds() / 3600
                
                if time_gap >= OVERNIGHT_GAP_HOURS:
                    # Found an overnight gap - mark the point before the gap as a stop
                    existing_stop_indices.append(prev_idx)

    # Handle overnight stops - check for existing ones first
    user_kept_existing_stops = False
    if existing_stop_indices:
        print(
            f"\n{Colors.INFO}Detected {Colors.HIGHLIGHT}{len(existing_stop_indices)}{Colors.RESET} existing overnight stop(s) in the GPX file."
        )

        # Convert indices to sleep_stops format
        sleep_stops = []
        for i, stop_idx in enumerate(existing_stop_indices):
            sleep_stops.append(
                {
                    "night": i + 1,
                    "point": all_points[stop_idx],
                    "target_distance": all_points[stop_idx]["cumulative_distance"],
                }
            )

        # Display detected overnight stops
        display_sleep_stops(
            sleep_stops, total_distance, "Existing overnight locations:"
        )

        # Ask if user wants to keep or recalculate
        print(f"\n{Colors.INFO}Would you like to keep these overnight locations?")
        keep_existing = (
            input("Press ENTER to keep or type 'yes' to recalculate: ").strip().lower()
        )

        if keep_existing == "yes":
            # Recalculate overnight stops
            if num_nights <= 0:
                print(f"\n{Colors.INFO}This is a day hike - no overnight stops needed.")
                sleep_stops = []
            else:
                print(f"\n{Colors.INFO}Recalculating for {num_nights} nights...")

                # Calculate daily distance
                daily_distance = total_distance / num_days
                print(f"{Colors.INFO}Average daily distance: {Colors.HIGHLIGHT}{daily_distance:.2f} km")

                # Find sleep-over locations
                sleep_stops = []
                for night in range(1, num_nights + 1):
                    target_distance = daily_distance * night
                    closest_point = find_closest_point(all_points, target_distance)
                    sleep_stops.append(
                        {
                            "night": night,
                            "point": closest_point,
                            "target_distance": target_distance,
                        }
                    )

                # Display the newly calculated sleep-over locations
                display_sleep_stops(
                    sleep_stops, total_distance, "New sleep-over locations:"
                )
        else:
            # User chose to keep existing stops
            user_kept_existing_stops = True
    else:
        # No existing stops detected, calculate as before
        if num_nights <= 0:
            print(f"\n{Colors.INFO}This is a day hike - no overnight stops needed.")
            sleep_stops = []
        else:
            print(f"\n{Colors.INFO}Number of nights: {Colors.HIGHLIGHT}{num_nights}")

            # Calculate daily distance
            daily_distance = total_distance / num_days
            print(f"{Colors.INFO}Average daily distance: {Colors.HIGHLIGHT}{daily_distance:.2f} km")

            # Find sleep-over locations
            sleep_stops = []
            for night in range(1, num_nights + 1):
                target_distance = daily_distance * night
                closest_point = find_closest_point(all_points, target_distance)
                sleep_stops.append(
                    {
                        "night": night,
                        "point": closest_point,
                        "target_distance": target_distance,
                    }
                )

            # Display proposed sleep-over locations
            display_sleep_stops(
                sleep_stops, total_distance, "Proposed sleep-over locations:"
            )

    # Allow user to adjust sleep-over locations (only for newly calculated stops)
    if sleep_stops and not user_kept_existing_stops:
        print(f"\n{Colors.INFO}Would you like to adjust any sleep-over locations?")
        adjust = (
            input("Press ENTER to continue or type 'yes' to adjust: ").strip().lower()
        )

        if adjust == "yes":
            for stop in sleep_stops:
                print(
                    f"\n{Colors.HIGHLIGHT}Night {stop['night']}{Colors.RESET} - Current: {Colors.INFO}{stop['point']['coords'][0]:.6f}, {stop['point']['coords'][1]:.6f}"
                )
                new_coords = input(
                    "Press ENTER to keep current coordinates or type new coordinates (lat,lon): "
                ).strip()

                if new_coords:
                    try:
                        lat, lon = parse_coordinates(new_coords)

                        # Find closest point to new coordinates
                        min_dist = float("inf")
                        closest_point = None
                        for point in all_points:
                            dist = safe_geodesic((lat, lon), point["coords"])
                            if dist < min_dist:
                                min_dist = dist
                                closest_point = point

                        stop["point"] = closest_point
                        print(
                            f"  {Colors.SUCCESS}Adjusted to nearest track point: {closest_point['coords'][0]:.6f}, {closest_point['coords'][1]:.6f}"
                        )
                        print(f"  {Colors.INFO}Distance from input: {min_dist*1000:.0f} meters")
                    except ValueError as e:
                        print(f"  {Colors.ERROR}Invalid input: {e}")
                    except Exception:
                        print(
                            f"  {Colors.ERROR}Error processing coordinates - keeping original location"
                        )

    # Extract route name from GPX metadata if available
    default_route_name = "Hiking Route"
    metadata_name = root.find(f".//{{{GPX_NAMESPACE}}}metadata/{{{GPX_NAMESPACE}}}name")
    if metadata_name is not None and metadata_name.text:
        default_route_name = metadata_name.text.strip()

    # Get route name
    route_name = get_user_input("Route name", default_route_name)

    # Validate the route before saving
    warnings = validate_gpx_data(all_points, sleep_stops, total_distance)
    if warnings:
        print(f"\n{Colors.WARNING}⚠️  Route validation warnings:")
        for warning in warnings:
            print(f"   {Colors.WARNING}- {warning}")
        proceed = input(f"\n{Colors.PROMPT}Do you want to continue anyway? (yes/no): {Colors.RESET}").strip().lower()
        if proceed != "yes":
            print(f"{Colors.WARNING}Exiting without saving.")
            return

    # Create new GPX structure matching Komoot's format
    print(f"\n{Colors.INFO}Creating GPX file...")
    new_root = create_komoot_compatible_gpx(
        all_points, sleep_stops, start_time, end_time, walking_speed, route_name
    )

    # Pretty print the XML
    indent_xml(new_root)

    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Extract base name from source
    if urlparse(source).scheme:
        # It's a URL, use a generic name
        base_name = "gpx_route"
    else:
        # It's a file path, use the base name
        base_name = os.path.splitext(os.path.basename(source))[0]

    default_output = f"{base_name}-{timestamp}.gpx"
    output_file = get_user_input("Output filename", default_output)

    # Save the modified GPX file
    tree = ET.ElementTree(new_root)
    tree.write(output_file, xml_declaration=True, encoding="UTF-8", method="xml")

    print(f"\n{Colors.SUCCESS}GPX route file saved as '{output_file}'")

    # Add this new section here:
    # Ask if user wants to split into daily files
    if sleep_stops:  # Only offer this option for multi-day hikes
        print(f"\n{Colors.INFO}Would you like to save each hiking day in a separate GPX file?")
        split_days = (
            input(
                "Press ENTER to keep as one file or type 'yes' to split each day as a file: "
            )
            .strip()
            .lower()
        )

        if split_days == "yes":
            # Extract base filename without extension
            base_filename = os.path.splitext(output_file)[0]

            print(f"\n{Colors.INFO}Creating daily GPX files...")
            daily_files = create_daily_gpx_files(
                all_points,
                sleep_stops,
                start_time,
                end_time,
                walking_speed,
                route_name,
                base_filename,
            )

            print(f"\n{Colors.SUCCESS}Created {len(daily_files)} daily GPX files:")
            for day_file in daily_files:
                print(
                    f"{Colors.SUCCESS}- Day {day_file['day']}: {day_file['filename']} ({day_file['distance']:.1f} km, {day_file['points']} points)"
                )

    # Continue with the rest of the function...
    print(f"\n{Colors.INFO}Total hiking days: {Colors.HIGHLIGHT}{num_days}")
    print(f"{Colors.INFO}Average daily distance: {Colors.HIGHLIGHT}{total_distance/num_days:.2f} km")
    print(
        f"{Colors.INFO}Average daily hiking time: {Colors.HIGHLIGHT}{(total_distance/num_days)/walking_speed:.1f} hours"
    )

    # Show final summary with sleep stops
    if sleep_stops:
        print(f"\n{Colors.BOLD}Final itinerary:")
        print(f"{Colors.INFO}Day 1: Start at {Colors.HIGHLIGHT}{start_time.strftime('%Y-%m-%d %H:%M')}")
        day1_dist = sleep_stops[0]["point"]["cumulative_distance"]
        print(
            f"  {Colors.SUCCESS}→ Walk {day1_dist:.1f} km to overnight stop at {sleep_stops[0]['point']['coords'][0]:.6f}, {sleep_stops[0]['point']['coords'][1]:.6f}"
        )

        for i in range(len(sleep_stops)):
            day_num = i + 2
            if i < len(sleep_stops) - 1:
                # Middle days start at 9:00
                day_start = (start_time + timedelta(days=i + 1)).replace(
                    hour=DEFAULT_START_HOUR, minute=0
                )
                print(f"{Colors.INFO}Day {day_num}: Start at {Colors.HIGHLIGHT}{day_start.strftime('%Y-%m-%d %H:%M')}")
                prev_dist = sleep_stops[i]["point"]["cumulative_distance"]
                next_dist = sleep_stops[i + 1]["point"]["cumulative_distance"]
                day_dist = next_dist - prev_dist
                print(
                    f"  {Colors.SUCCESS}→ Walk {day_dist:.1f} km to overnight stop at {sleep_stops[i+1]['point']['coords'][0]:.6f}, {sleep_stops[i+1]['point']['coords'][1]:.6f}"
                )
            else:
                # Last day - calculate start time based on end time
                last_dist = (
                    total_distance - sleep_stops[i]["point"]["cumulative_distance"]
                )
                last_hours = last_dist / walking_speed
                last_day_start = end_time - timedelta(hours=last_hours)
                print(
                    f"{Colors.INFO}Day {day_num}: Start at {Colors.HIGHLIGHT}{last_day_start.strftime('%Y-%m-%d %H:%M')}"
                )
                print(f"  {Colors.SUCCESS}→ Walk {last_dist:.1f} km to finish")
                print(f"\n{Colors.SUCCESS}Arrive at {Colors.HIGHLIGHT}{end_time.strftime('%Y-%m-%d %H:%M')}")

    # Save markdown itinerary
    md_filename = os.path.splitext(output_file)[0] + ".md"
    save_markdown_itinerary(
        md_filename,
        start_time,
        end_time,
        total_distance,
        sleep_stops,
        walking_speed,
        all_points,
    )

    # Save KML file
    kml_filename = os.path.splitext(output_file)[0] + ".kml"
    save_kml_file(
        kml_filename,
        all_points,
        sleep_stops,
        route_name,
        start_time,
        end_time,
    )

    # Save PNG image
    png_filename = os.path.splitext(output_file)[0] + ".png"
    save_route_image(
        png_filename,
        all_points,
        sleep_stops,
        route_name,
    )

    print(f"\n{Colors.BOLD}Files created:")
    print(f"{Colors.SUCCESS}- GPX file: {Colors.HIGHLIGHT}{output_file}")

    # Add daily files to the summary if they exist
    if "daily_files" in locals() and daily_files:
        for day_file in daily_files:
            print(f"{Colors.SUCCESS}- Day {day_file['day']} GPX: {Colors.HIGHLIGHT}{day_file['filename']}")

    print(f"{Colors.SUCCESS}- Markdown itinerary: {Colors.HIGHLIGHT}{md_filename}")
    print(f"{Colors.SUCCESS}- KML file: {Colors.HIGHLIGHT}{kml_filename}")
    print(f"{Colors.SUCCESS}- PNG image: {Colors.HIGHLIGHT}{png_filename}")


if __name__ == "__main__":
    main()
