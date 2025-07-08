from setuptools import setup, find_packages
import os


# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


setup(
    name="gpx-route-timer",
    version="0.1.0",
    author="pattespatte",
    description="Add timestamps to GPX files for multi-day hikes",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/pattespatte/gpx-route-timer",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.31.0",
        "geopy>=2.4.1",
    ],
    entry_points={
        "console_scripts": [
            "gpx-route-timer=gpx_route_timer.main:main",
        ],
    },
    include_package_data=True,
)
