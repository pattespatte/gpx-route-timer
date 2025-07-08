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

## Installation

```bash
git clone https://github.com/pattespatte/gpx-route-timer
cd gpx-route-timer
# Direct invocation (without installation): If you do not prefer not to install the package, then just run:
python src/gpx-route-timer/__init__.py [GPX_FILE_OR_URL] [options]
```

### Alternatively, you can install the package using pip

```bash
pip install -r requirements.txt
pip install -e .
```

## Usage

After installing the package, the `gpx-route-timer` command should be available in your terminal:

```bash
gpx-route-timer [GPX_FILE_OR_URL] [options]
```

## Example

To run the tool with the example GPX file:

```bash
gpx-route-timer example.gpx
```

Alternatively, to use the example GPX file directly from the repository:

```bash
gpx-route-timer https://github.com/pattespatte/gpx-route-timer/raw/main/misc/example.gpx
```
