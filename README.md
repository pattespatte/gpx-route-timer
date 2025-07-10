# GPX Route Timer

Add timestamps to GPX files for multi-day hikes with automatic overnight stop detection and itinerary generation.

## Features

- **Multi-day route planning**: Automatically calculate overnight stops for multi-day hikes
- **Timestamp generation**: Add realistic timestamps to GPX files for services like Komoot
- **Existing stop detection**: Detect and preserve existing overnight stops from GPX timestamps
- **Interactive customization**: Adjust start/end times and overnight locations
- **Multiple output formats**:
  - GPX files with timestamps
  - Markdown itineraries with daily breakdowns
  - **KML files for Google Earth visualization**
- **Map integration**: Generate Google Maps links for all waypoints and route overview
- **Route validation**: Check for realistic daily distances and hiking times
- **Flexible input**: Support for both local files and URLs

## Requirements

- Python 3.8 or higher
- pip

## Installation

### Option 1: Using a Virtual Environment (Recommended)

```bash
# Clone the repository
git clone https://github.com/pattespatte/gpx-route-timer
cd gpx-route-timer

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -r requirements.txt
pip install -e .
```

## Option 2: Direct Usage (No Installation)

```bash
# Clone the repository

git clone https://github.com/pattespatte/gpx-route-timer
cd gpx-route-timer

# Install dependencies

pip install -r requirements.txt

# Run directly

python src/gpx_route_timer/__init__.py [GPX_FILE_OR_URL] [options]
```

## Usage

After installation, use the `gpx-route-timer` command:

```bash
gpx-route-timer [GPX_FILE_OR_URL] [options]
# Process a local GPX file:
gpx-route-timer misc/example.gpx
# Process a GPX file from a URL:
gpx-route-timer https://github.com/pattespatte/gpx-route-timer/raw/main/misc/example.gpx
```
