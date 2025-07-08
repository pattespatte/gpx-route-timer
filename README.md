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
pip install -r requirements.txt
```

## Usage

```bash
python gpx_route_timer.py [GPX_FILE_OR_URL] [options]
```

## Example

```bash
python src/gpx_route_timer/main.py example.gpx
```
