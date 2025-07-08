from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="gpx-route-timer",
    version="0.1.0",
    author="Patrik Wästlund",
    author_email="p@wastlund.net",
    description="A tool to plan multi-day hikes by adding timestamps to GPX files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pattespatte/gpx-route-timer",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "gpx-route-timer=gpx_route_timer.main:main",
        ],
    },
)
# This setup script is used to package the hiking planner tool "GPX Route Timer".
