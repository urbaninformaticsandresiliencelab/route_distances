#!/usr/bin/env python3

import datetime
import googlemaps
import json
import requests

# Default entrypoint to be used for non-Google services when none is defined
DEFAULT_ENTRYPOINT = "localhost:8000"

# Default timeout
DEFAULT_TIMEOUT = 30

# Number of attempts to make before abandoning a calculation
MAX_ATTEMPTS = 5

class Distances():
    """ Base class for distance calculators

    Attributes:
        mode_map: A dictionary of key remaps, to be defined by subclasses. For
            example, the following map would map drive/walk/transit/bike to
            valid OpenTripPlanner modes:

                self.mode_map = {
                    "drive": "WALK,CAR",
                    "walk": "WALK",
                    "transit": "WALK,TRANSIT",
                    "bike": "WALK,BICYCLE"
                }

        verbose: A boolean describing whether or not verbose output should be
            enabled.
        timeout: An integer that describes how long until a route times out.
    """

    def __init__(self, timeout = DEFAULT_TIMEOUT, verbose = False,
                 fail_fast = True):
        """ Initializes Distances class and all child classes

        Args:
            verbose: A boolean that toggles verbosity of output.
            timeout: An integer that describes how long until a route times out.
            fail_fast: A boolean that toggles whether to raise an exception or
                return False when a route fails to calculate. The exception is
                the exception returned by the requests library.
        """

        self.verbose = verbose
        self.timeout = timeout
        self.fail_fast = fail_fast

    def log(self, string):
        """ Prints a string if verbose mode is enabled

        Args:
            string: A string to be printed if self.verbose is True.
        """
        if (self.verbose):
            print("%s %s" % (datetime.datetime.now().isoformat(), string))

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
        """ Frontend function for self.route

        Wrapper function that sits between the end user and self.route, as
        defined by child classes. self.distance passes all arguments to
        self.route and handles retries.

        """

        exception = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                if (attempt > 0):
                    self.log("Retrying (attempt %d)" % (attempt + 1))
                return self.route(*args, **kwargs)
            except Exception as error:
                exception = error
                print("Error: %s" % error)

        self.log("Max attempts reached (%d)" % MAX_ATTEMPTS)

        if (self.fail_fast):
            raise exception
        else:
            return False

class GoogleMapsDistances(Distances):
    """ Subclass of Distances that uses the Google Maps Distances Matrix API as a
    backend

    Attributes:
        gmaps: An instance of googlemaps.Client used for scraping.
    """

    def __init__(self, api_key = None, client_id = None, client_secret = None,
                 *args, **kwargs):
        """ Initialize GoogleMapsDistances object

        Args:
            api_key: The Google Maps API key to be used to initialize the
                self.gmaps googlemaps.Client object. Either this or both
                client_id and client_secret must be provided. According to the
                docs, client_id and client_secret are needed "for Maps API for
                Work customers".
            client_id: The Google Maps API for Work client ID.
            client_secret:: The Google Maps API for Work client secret.
        """

        Distances.__init__(self, *args, **kwargs)
        if (api_key is not None):
            self.gmaps = googlemaps.Client(key = api_key,
                                           timeout = self.timeout)
        else:
            self.gmaps = googlemaps.Client(client_id = client_id,
                                           client_secret = client_secret,
                                           timeout = self.timeout)
        self.mode_map = {
            "bike": "bicycling",
            "drive": "driving",
            "transit": "transit",
            "walk": "walking"
        }

    def route(self, orig_long, orig_lat, dest_long, dest_lat, mode = "walk"):
        """ routes the distance between two coordinates

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            dest_long: The destination longitude.
            dest_lat: The destination latitude.
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API.

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

        self.log(result)
        if (result["status"] == "OK"):
            return {
                "duration": result["rows"][0]["elements"][0]["duration"]["value"],
                "distance": result["rows"][0]["elements"][0]["distance"]["value"]
            }

        return False

    def route_multi(self, orig_long, orig_lat, destinations, mode = "walk"):
        """ routes the distance between one origin and multiple destinations

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            destinations: An iterable containing (long, lat) tuples or lists
            mode: A key of the self.mode_map dictionary that will be remapped
                to a different string and passed to the API.

        Returns:
            A list of dictionaries formatted like the output of self.distance().
        """

        self.log("Sending request to Google")
        result = self.gmaps.distance_matrix(
            origins = (orig_lat, orig_long),
            destinations = [(coord[1], coord[0]) for coord in destinations],
            units = "metric",
            mode = self.map_mode(mode)
        )
        self.log("Response: %s" % result)

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

    def __init__(self, entrypoint = DEFAULT_ENTRYPOINT, *args, **kwargs):
        """ Initializes the OTPDistances class

        Args:
            entrypoint: The base URL containing the API entrypoint.
        """

        Distances.__init__(self, *args, **kwargs)
        self.entrypoint = entrypoint
        self.mode_map = {
            "bike": "WALK,BICYCLE",
            "drive": "WALK,CAR",
            "transit": "WALK,TRANSIT",
            "walk": "WALK"
        }

    def route(self, from_long, from_lat, to_long, to_lat, mode = "walk"):
        """ routes the distance between two coordinates

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            dest_long: The destination longitude.
            dest_lat: The destination latitude.
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API.

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """

        url = ("http://%s/otp/routers/default/plan"
               "?fromPlace=%f,%f&toPlace=%f,%f&mode=%s" % (
            self.entrypoint,
            from_lat, from_long, to_lat, to_long,
            self.map_mode(mode)
        ))

        self.log("Sending request: %s" % url)
        response = requests.get(url, timeout = self.timeout)
        self.log("Response: %s" % response.content.decode())

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

    def __init__(self, entrypoint = DEFAULT_ENTRYPOINT, *args, **kwargs):
        """ Initializes the OSRMDistances class

        Args:
            entrypoint: The base URL containing the API entrypoint.
        """

        Distances.__init__(self, *args, **kwargs)
        self.entrypoint = entrypoint
        self.mode_map = {
            "bike": "bike",
            "drive": "car",
            "transit": "none",
            "walk": "foot"
        }

    def route(self, from_long, from_lat, to_long, to_lat, mode = "walk"):
        """ routes the distance between two coordinates

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            dest_long: The destination longitude.
            dest_lat: The destination latitude.
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API.

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """


        url = ("http://%s/route/v1/%s/"
               "%f,%f;%f,%f" % (
            self.entrypoint,
            self.map_mode(mode),
            from_long, from_lat, to_long, to_lat
        ))

        self.log("Sending request: %s" % url)
        response = requests.get(url, timeout = self.timeout)
        self.log("Response: %s" % response.content.decode())

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

    def __init__(self, entrypoint = DEFAULT_ENTRYPOINT, *args, **kwargs):
        """ Initializes the ValhallaDistances class

        Args:
            entrypoint: The base URL containing the API entrypoint.
        """

        Distances.__init__(self, *args, **kwargs)
        self.entrypoint = entrypoint
        self.mode_map = {
            "bike": "bicycle",
            "drive": "auto",
            "transit": "multimodal",
            "walk": "pedestrian"
        }

    def route(self, from_long, from_lat, to_long, to_lat, mode = "walk",
                  avoid = []):
        """ routes the distance between two coordinates

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            dest_long: The destination longitude.
            dest_lat: The destination latitude.
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API.
            avoid: An array of (long, lat) pairs to be avoided.

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """

        request_json = {
            "locations": [
                {"lon": from_long, "lat": from_lat},
                {"lon": to_long, "lat": to_lat},
            ],
            "costing": self.map_mode(mode),
            "directions_options": {
                "units": "kilometers"
            }
        }

        if (len(avoid) > 0):
            request_json["avoid_locations"] = [
                {"lat": x[0], "lon": x[1]} for x in avoid
            ]

        self.log("Sending request JSON to %s: %s" % (self.entrypoint,
                                                     request_json))
        response = requests.post(
            "http://%s/route" % self.entrypoint,
            json = request_json,
            timeout = self.timeout
        )
        self.log("Response: %s" % response.content.decode())

        if (response.status_code == 200):
            content = json.loads(response.content.decode())
            if (not "error" in content):
                return {
                    "distance": content["trip"]["legs"][0]["summary"]["length"] * 1000,
                    "duration": content["trip"]["legs"][0]["summary"]["time"]
                }

        return False

