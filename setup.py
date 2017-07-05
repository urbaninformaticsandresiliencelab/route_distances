#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name = "route_distances",
    version = "1.8.0",
    license = "MIT",
    description = "Classes for getting the distance of a route between two"
                  "places using various different services",
    packages = ["route_distances"],
    install_requires = ["googlemaps", "requests", "shapely"]
)
