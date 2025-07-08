# GPX Route Timer

A Python tool to plan multi-day hikes by adding timestamps to GPX files.

## Features

- Calculate total route distance and suggest overnight stops
- Output a GPX file with timestamps
- Generate a Markdown itinerary with daily breakdowns and map links
- Detect existing overnight stops based on time gaps in the GPX
- Interactively set or adjust start/end times and overnight locations
- Validate route for realistic daily distances
- Download or load a GPX file from a URL or local path

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
