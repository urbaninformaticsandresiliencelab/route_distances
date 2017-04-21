#!/usr/bin/env python3

import googlemaps
import json
import requests

# Default entrypoint to be used for non-Google services when none is defined
DEFAULT_ENTRYPOINT = "localhost:8000"

# Number of attempts to make before abandoning a calculation
MAX_ATTEMPTS = 5

class Distances():
    """ Base class for distance calculators

    Attributes:
        mode_map: A dictionary of key remaps, to be defined by subclasses. For
            example, the following map would map drive/walk/transit/bike to
            valid OpenTripPlanner modes

                self.mode_map = {
                    "drive": "WALK,CAR",
                    "walk": "WALK",
                    "transit": "WALK,TRANSIT",
                    "bike": "WALK,BICYCLE"
                }
    """

    def map_mode(self, mode):
        """ Remaps an input mode into a mode usable by an API

        Args:
            mode: A string to be remapped.

        Returns:
            The remapped string according to the class's mode_map attribute.

        Raises:
            LookupError: A mode to be remapped was not found in this class's
                self.mode_map dictionary.
        """
        if (mode in self.mode_map):
            return self.mode_map[mode]
        else:
            print("Invalid mode \"%s\"" % mode)
            raise LookupError

    def distance(self, *args, **kwargs):
        """ Frontend function for self.calculate

        Wrapper function that sits between the end user and self.calculate, as
        defined by child classes. self.distance passes arguments to
        self.calculate and handles retries

        """

        for attempt in range(MAX_ATTEMPTS):
            try:
                return self.calculate(*args, **kwargs)
            except Exception as error:
                print("Error: %s" % error)
                print("Retrying (attempt %d)" % (attempt + 1))

        print("Max attempts exceeded")
        return False

class GoogleMapsDistances(Distances):
    """ Subclass of Distances that uses the Google Maps Distances Matrix API as a
    backend

    Attributes:
        gmaps: An instance of googlemaps.Client used for scraping
    """

    def __init__(self, api_key):
        """ Initialize GoogleMapsDistances object

        Args:
            api_key: The Google Maps API key to be used to initialize the
                self.gmaps googlemaps.Client object
        """

        self.gmaps = googlemaps.Client(key = api_key, timeout = 600)
        self.mode_map = {
            "bike": "bicycling",
            "drive": "driving",
            "transit": "transit",
            "walk": "walking"
        }

    def calculate(self, orig_long, orig_lat, dest_long, dest_lat, mode = "walk"):
        """ Calculates the distance between two coordinates

        Args:
            orig_long: The origin longitude
            orig_lat: The origin latitude
            dest_long: The destination longitude
            dest_lat: The destination latitude
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """

        result = self.gmaps.distance_matrix(
            origins = (orig_lat, orig_long),
            destinations = (dest_lat, dest_long),
            units = "metric",
            mode = self.map_mode(mode)
        )

        if (result["status"] == "OK"):
            return {
                "duration": result["rows"][0]["elements"][0]["duration"]["value"],
                "distance": result["rows"][0]["elements"][0]["distance"]["value"]
            }

        return False

    def calculate_multi(self, orig_long, orig_lat, destinations, mode = "walk"):
        """ Calculates the distance between one origin and multiple destinations

        Args:
            orig_long: The origin longitude
            orig_lat: The origin latitude
            destinations: An iterable containing (long, lat) tuples or lists
            mode: A key of the self.mode_map dictionary that will be remapped
                to a different string and passed to the API

        Returns:
            A list of dictionaries formatted like the output of self.distance()
        """

        result = self.gmaps.distance_matrix(
            origins = (orig_lat, orig_long),
            destinations = [(coord[1], coord[0]) for coord in destinations],
            units = "metric",
            mode = self.map_mode(mode)
        )

        if (result["status"] == "OK"):
            results = []
            for element in result["rows"][0]["elements"]:
                results.append({
                    "duration": element["duration"]["value"],
                    "distance": element["distance"]["value"]
                })
            return results

        return False

class OTPDistances(Distances):
    """ Subclass of Distances that uses OpenTripPlanner as a backend """

    def __init__(self, entrypoint = DEFAULT_ENTRYPOINT):
        """ Initializes the OTPDistances class

        Args:
            entrypoint: The base URL containing the API entrypoint
        """

        self.entrypoint = entrypoint
        self.mode_map = {
            "bike": "WALK,BICYCLE",
            "drive": "WALK,CAR",
            "transit": "WALK,TRANSIT",
            "walk": "WALK"
        }

    def calculate(self, from_long, from_lat, to_long, to_lat, mode = "walk"):
        """ Calculates the distance between two coordinates

        Args:
            orig_long: The origin longitude
            orig_lat: The origin latitude
            dest_long: The destination longitude
            dest_lat: The destination latitude
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """

        response = requests.get(
            "http://%s/otp/routers/default/plan"
            "?fromPlace=%f,%f&toPlace=%f,%f&mode=%s" % (
                self.entrypoint,
                from_lat, from_long, to_lat, to_long,
                self.map_mode(mode)
            )
        )

        if (response.status_code == 200):
            content = json.loads(response.content.decode())
            if (not "error" in content):
                return {
                    "duration": content["plan"]["itineraries"][0]["legs"][0]["duration"],
                    "distance": content["plan"]["itineraries"][0]["legs"][0]["distance"],
                }

        return False

class OSRMDistances(Distances):
    """ Subclass of Distances that uses OSRM as a backend """

    def __init__(self, entrypoint = DEFAULT_ENTRYPOINT):
        """ Initializes the OSRMDistances class

        Args:
            entrypoint: The base URL containing the API entrypoint
        """

        self.entrypoint = entrypoint
        self.mode_map = {
            "bike": "bike",
            "drive": "car",
            "transit": "none",
            "walk": "foot"
        }

    def calculate(self, from_long, from_lat, to_long, to_lat, mode = "walk"):
        """ Calculates the distance between two coordinates

        Args:
            orig_long: The origin longitude
            orig_lat: The origin latitude
            dest_long: The destination longitude
            dest_lat: The destination latitude
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """


        response = requests.get(
            "http://%s/route/v1/%s/"
            "%f,%f;%f,%f" % (
                self.entrypoint,
                self.map_mode(mode),
                from_long, from_lat, to_long, to_lat
            )
        )

        if (response.status_code == 200):
            content = json.loads(response.content.decode())
            if (not "error" in content):
                return {
                    "distance": content["routes"][0]["distance"],
                    "duration": content["routes"][0]["duration"],
                }

        return False

class ValhallaDistances(Distances):
    """ Subclass of Distances that uses Valhalla as a backend """

    def __init__(self, entrypoint = DEFAULT_ENTRYPOINT):
        """ Initializes the ValhallaDistances class

        Args:
            entrypoint: The base URL containing the API entrypoint
        """

        self.entrypoint = entrypoint
        self.mode_map = {
            "bike": "bicycle",
            "drive": "auto",
            "transit": "multimodal",
            "walk": "pedestrian"
        }

    def calculate(self, from_long, from_lat, to_long, to_lat, mode = "walk"):
        """ Calculates the distance between two coordinates

        Args:
            orig_long: The origin longitude
            orig_lat: The origin latitude
            dest_long: The destination longitude
            dest_lat: The destination latitude
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """

        response = requests.post(
            "http://%s/route" % self.entrypoint,
            json = {
                "locations": [
                    {"lon": from_long, "lat": from_lat},
                    {"lon": to_long, "lat": to_lat},
                ],
                "costing": self.map_mode(mode),
                "directions_options": {
                    "units": "kilometers"
                }
            }
        )

        if (response.status_code == 200):
            content = json.loads(response.content.decode())
            if (not "error" in content):
                return {
                    "distance": content["trip"]["legs"][0]["summary"]["length"] * 1000,
                    "duration": content["trip"]["legs"][0]["summary"]["time"]
                }

        return False

