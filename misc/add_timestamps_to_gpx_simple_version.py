#!/usr/bin/env python3
"""GPX Route Timer - Add timestamps to GPX files for multi-day hikes"""

import sys
import subprocess


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
    required = {"requests": "requests", "geopy": "geopy"}

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
from datetime import datetime, timedelta
from geopy.distance import geodesic
import os
from urllib.parse import quote, urlparse

# Register the GPX namespace to avoid ns0: prefix
ET.register_namespace("", "http://www.topografix.com/GPX/1/1")


def get_user_input(prompt, default):
    """Get user input with a default value"""
    user_input = input(f"{prompt} [default: {default}]: ").strip()
    return user_input if user_input else default


def format_map_link(lat, lon):
    """Create a Google Maps link for coordinates"""
    return f"https://www.google.com/maps?q={lat},{lon}"


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


def load_gpx_content(source):
    """Load GPX content from either a URL or local file path"""
    # Check if it's a URL
    parsed = urlparse(source)
    is_url = parsed.scheme in ("http", "https")

    if is_url:
        print(f"\nDownloading GPX file from URL...")
        try:
            response = requests.get(source)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            sys.exit(1)
    else:
        # Treat as local file path
        print(f"\nLoading GPX file from local path...")
        try:
            # Expand user home directory if needed
            file_path = os.path.expanduser(source)
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)


def main():
    # Get GPX source (URL or file path)
    default_source = "https://gist.githubusercontent.com/pattespatte/272d9d021973435f75b09ab191af0db2/raw/2025-07-04-2378484963-from-laholm-to-helsingborg-no-times.gpx"
    print("\nGPX source can be either a URL (http://...) or a local file path")
    source = get_user_input("GPX source (URL or file path)", default_source)

    # Load GPX content
    gpx_xml = load_gpx_content(source)

    # Parse XML with proper namespace handling
    try:
        root = ET.fromstring(gpx_xml)
    except ET.ParseError as e:
        print(f"Error parsing GPX file: {e}")
        sys.exit(1)

    # Extract all trackpoints - no namespace prefix needed in XPath
    all_points = []
    for trk in root.findall(".//{http://www.topografix.com/GPX/1/1}trk"):
        for seg in trk.findall(".//{http://www.topografix.com/GPX/1/1}trkseg"):
            for pt in seg.findall(".//{http://www.topografix.com/GPX/1/1}trkpt"):
                lat = float(pt.get("lat"))
                lon = float(pt.get("lon"))
                all_points.append(
                    {"element": pt, "coords": (lat, lon), "cumulative_distance": 0}
                )

    if not all_points:
        print("Error: No track points found in GPX file")
        sys.exit(1)

    print(f"Found {len(all_points)} track points")

    # Calculate cumulative distance
    total_distance = 0
    for i in range(len(all_points)):
        if i > 0:
            dist = geodesic(all_points[i - 1]["coords"], all_points[i]["coords"]).km
            total_distance += dist
        all_points[i]["cumulative_distance"] = total_distance

    print(f"\nTotal distance: {total_distance:.2f} km")

    # Get start and end times
    default_start = "2025-08-17T16:00"
    start_time_str = get_user_input("Start time (YYYY-MM-DDTHH:MM)", default_start)
    try:
        start_time = datetime.fromisoformat(start_time_str)
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DDTHH:MM")
        sys.exit(1)

    default_end = "2025-08-21T16:00"
    end_time_str = get_user_input("End time (YYYY-MM-DDTHH:MM)", default_end)
    try:
        end_time = datetime.fromisoformat(end_time_str)
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DDTHH:MM")
        sys.exit(1)

    # Calculate hiking parameters
    total_hours = (end_time - start_time).total_seconds() / 3600
    walking_speed = 4.0  # km/h
    walking_hours_needed = total_distance / walking_speed

    print(f"\nTotal time available: {total_hours:.1f} hours")
    print(
        f"Walking time needed at {walking_speed} km/h: {walking_hours_needed:.1f} hours"
    )

    if walking_hours_needed > total_hours:
        print("\nWarning: Not enough time to complete the hike at the specified speed!")
        return

    # Calculate number of nights
    num_days = (end_time.date() - start_time.date()).days + 1
    num_nights = num_days - 1

    if num_nights <= 0:
        print("\nThis is a day hike - no overnight stops needed.")
        sleep_stops = []
    else:
        print(f"\nNumber of nights: {num_nights}")

        # Calculate daily distance
        daily_distance = total_distance / num_days
        print(f"Average daily distance: {daily_distance:.2f} km")

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
        print("\nProposed sleep-over locations:")
        for stop in sleep_stops:
            lat, lon = stop["point"]["coords"]
            actual_dist = stop["point"]["cumulative_distance"]
            print(f"\nNight {stop['night']}:")
            print(
                f"  Distance from start: {actual_dist:.2f} km (target: {stop['target_distance']:.2f} km)"
            )
            print(f"  Coordinates: {lat:.6f}, {lon:.6f}")
            print(f"  View on map: {format_map_link(lat, lon)}")

        # Allow user to adjust sleep-over locations
        print("\nWould you like to adjust any sleep-over locations?")
        adjust = (
            input("Enter 'yes' to adjust or press Enter to continue: ").strip().lower()
        )

        if adjust == "yes":
            for stop in sleep_stops:
                print(
                    f"\nNight {stop['night']} - Current: {stop['point']['coords'][0]:.6f}, {stop['point']['coords'][1]:.6f}"
                )
                new_coords = input(
                    "Enter new coordinates (lat,lon) or press Enter to keep: "
                ).strip()

                if new_coords:
                    try:
                        lat, lon = map(float, new_coords.split(","))
                        # Find closest point to new coordinates
                        min_dist = float("inf")
                        closest_point = None
                        for point in all_points:
                            dist = geodesic((lat, lon), point["coords"]).km
                            if dist < min_dist:
                                min_dist = dist
                                closest_point = point

                        stop["point"] = closest_point
                        print(
                            f"  Adjusted to nearest track point: {closest_point['coords'][0]:.6f}, {closest_point['coords'][1]:.6f}"
                        )
                        print(f"  Distance from input: {min_dist*1000:.0f} meters")
                    except:
                        print("  Invalid input - keeping original location")

    # Add timestamps to all points
    print("\nAdding timestamps to track points...")

    # Calculate actual walking schedule
    current_day = 0
    day_start_time = start_time
    day_distance_walked = 0

    for i, point in enumerate(all_points):
        # Check if we've reached a sleep stop
        for stop in sleep_stops:
            if i > 0 and stop["point"] == point:
                # Start new day
                current_day += 1
                day_start_time = start_time + timedelta(days=current_day)
                day_distance_walked = point["cumulative_distance"]

        # Calculate time for this point
        distance_today = point["cumulative_distance"] - day_distance_walked
        hours_today = distance_today / walking_speed
        current_time = day_start_time + timedelta(hours=hours_today)

        # Check for existing time element (with or without namespace)
        existing_time = None
        for child in point["element"]:
            if child.tag == "time" or child.tag.endswith("}time"):
                existing_time = child
                break

        if existing_time is not None:
            # Update existing time element
            existing_time.text = current_time.isoformat() + "Z"
        else:
            # No existing time element, create one
            time_elem = ET.SubElement(point["element"], "time")
            time_elem.text = current_time.isoformat() + "Z"

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
    ET.ElementTree(root).write(output_file, xml_declaration=True, encoding="utf-8")

    print(f"\nGPX file saved as '{output_file}'")
    print(f"Total hiking days: {num_days}")
    print(f"Average daily distance: {total_distance/num_days:.2f} km")
    print(
        f"Average daily hiking time: {(total_distance/num_days)/walking_speed:.1f} hours"
    )

    # Show final summary with sleep stops
    if sleep_stops:
        print("\nFinal itinerary:")
        print(f"Day 1: Start at {start_time.strftime('%Y-%m-%d %H:%M')}")
        for i, stop in enumerate(sleep_stops):
            lat, lon = stop["point"]["coords"]
            dist = stop["point"]["cumulative_distance"]
            print(f"  → Walk {dist:.1f} km to overnight stop at {lat:.6f}, {lon:.6f}")
            print(
                f"Day {i+2}: Start at {(start_time + timedelta(days=i+1)).strftime('%Y-%m-%d %H:%M')}"
            )
        print(
            f"  → Walk {total_distance - sleep_stops[-1]['point']['cumulative_distance']:.1f} km to finish"
        )
        print(f"Arrive at {end_time.strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()
