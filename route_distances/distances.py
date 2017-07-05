#!/usr/bin/env python3

from shapely import geometry
import datetime
import googlemaps
import json
import requests
import time

try:
    from . import staticmaps
except:
    import staticmaps

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
        staticmaps: A staticmaps.Constructor object, only present if verbose is
            true. This is used to visualize isochrones.
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

        if (verbose):
            self.staticmaps = staticmaps.Constructor()

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
    """ Subclass of Distances that uses the Google Maps Distances Matrix API as
    a backend

    Attributes:
        gmaps: An instance of googlemaps.Client used for scraping.
        for_work: Tells whether or not a Google Maps API for Work account was
            used to authenticate. This must be true to use the departure_time
            argument in the route function.
        period_start: The seconds in Unix time since the current scraping
            period started.
        requests_this_period: The number of requests made in the current
            period.
        request_delay: The number of seconds to sleep between requests.
    """

    def __init__(self, api_key = None, client_id = None, client_secret = None,
                 requests_this_period = 0, requests_per_period = 100000,
                 period_length = 60*60*24, request_delay = 0.5,
                 *args, **kwargs):
        """ Initialize GoogleMapsDistances object

        Args:
            api_key: The Google Maps API key to be used to initialize the
                self.gmaps googlemaps.Client object. Either this or both
                client_id and client_secret must be provided. According to the
                docs, client_id and client_secret are needed "for Maps API for
                Work customers".
            client_id: The Google Maps API for Work client ID.
            client_secret: The Google Maps API for Work client secret.
            requests_this_period: The number of requests made this period.
            requests_per_period: The number of requests that can be made per
                period. The default is taken from the documentation at
                https://developers.google.com/maps/premium/usage-limits, in the
                Web service APIs section.
            period_length: The length of a period, the default being 24 hours.
            request_delay: The number of seconds to sleep between requests.
        """

        Distances.__init__(self, *args, **kwargs)

        if (api_key is not None):
            self.gmaps = googlemaps.Client(key = api_key,
                                           timeout = self.timeout)
        else:
            self.gmaps = googlemaps.Client(client_id = client_id,
                                           client_secret = client_secret,
                                           timeout = self.timeout)
            self.for_work = True

        self.period_start = None
        self.requests_this_period = requests_this_period
        self.requests_per_period = requests_per_period
        self.period_length = period_length
        self.request_delay = request_delay

        self.mode_map = {
            "bike": "bicycling",
            "drive": "driving",
            "transit": "transit",
            "walk": "walking"
        }

    def rate_limit(self):
        """ Handles rate limiting, holding up the script if necessary """

        self.requests_this_period += 1

        # Don't sleep on the first request
        if (self.period_start is None):
            self.period_start = time.time()
        else:
            time.sleep(self.request_delay)

        if (self.requests_this_period >= self.requests_per_period):
            next_period = self.period_start + self.period_length
            time_until_next_period = next_period - time.time()

            print("Reached max requests per period (%d >= %d)" % (
                self.requests_this_period, self.requests_per_period
            ))
            print("Sleeping %d seconds until next period (%s)" % (
                time_until_next_period,
                datetime.datetime.fromtimestamp(next_period).isoformat()
            ))

            time.sleep(time_until_next_period)

        if (time.time() >= self.period_start + self.period_length):
            self.period_start = time.time()
            self.requests_this_period = 0

    def route(self, orig_long, orig_lat, dest_long, dest_lat, mode = "walk",
              departure_time = None):
        """ Routes the distance between two coordinates

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            dest_long: The destination longitude.
            dest_lat: The destination latitude.
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API.
            departure_time: A datetime.datetime object. From the Google Maps
                API Python client docs:

                    Specifies the desired time of departure as seconds since
                    midnight, January 1, 1970 UTC. The departure time may be
                    specified by Google Maps API for Work customers to receive
                    trip duration considering current traffic conditions. The
                    departure_time must be set to within a few minutes of the
                    current time.

                If this is specified, then the traffic-adjusted travel time is
                returned. The client must be authorized with a client ID and
                client secret instead of an API key for this to work.

        Returns:
            A dictionary containing the total duration in the "duration" key and
                the total distance in the "distance" key if there are no errors;
                False if there are errors. Distance is in meters; duration is in
                seconds.
        """

        self.rate_limit()

        if (departure_time):

            self.log("Sending live traffic-adjusted request to Google")
            result = self.gmaps.distance_matrix(
                origins = (orig_lat, orig_long),
                destinations = (dest_lat, dest_long),
                units = "metric",
                mode = self.map_mode(mode),
                departure_time = departure_time
            )

        else:

            self.log("Sending request to Google")
            result = self.gmaps.distance_matrix(
                origins = (orig_lat, orig_long),
                destinations = (dest_lat, dest_long),
                units = "metric",
                mode = self.map_mode(mode)
            )

        self.log("Response: %s" % result)
        if (result["status"] == "OK"):
            return {
                "duration": result["rows"][0]["elements"][0]["duration"]["value"],
                "distance": result["rows"][0]["elements"][0]["distance"]["value"]
            }

        return False

    def route_multi(self, orig_long, orig_lat, destinations, mode = "walk"):
        """ Routes the distance between one origin and multiple destinations

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

    def route(self, from_long, from_lat, to_long, to_lat, mode = "walk",
              departure_time = None):
        """ Routes the distance between two coordinates

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            dest_long: The destination longitude.
            dest_lat: The destination latitude.
            mode: A key of the self.mode_map dictionary that will be remapped to
                a different string and passed to the API.
            departure_time: A datetime.datetime object corresponding to the
                desired departure time.

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

        if (departure_time):
            #url += "&dateTime=%d" % (departure_time.timestamp() * 1000)
            url = "&".join([
                url,
                "date=%s" % (departure_time.strftime("%Y-%m-%d")),
                "time=%s" % (departure_time.strftime("%H:%M"))
            ])

        self.log("Sending request: %s" % url)
        response = requests.get(url, timeout = self.timeout)
        data = response.content.decode()
        self.log("Response: %s" % data)

        if (response.status_code == 200):
            content = json.loads(data)
            if (not "error" in content):
                return {
                    "duration": content["plan"]["itineraries"][0]["duration"],
                    "distance": sum([
                        leg["distance"]
                        for leg in content["plan"]["itineraries"][0]["legs"]
                    ]),
                }

        return False

    def isochrone(self, from_long, from_lat, max_time = None,
                  max_distance = None, mode = "walk"):
        """ Generate an isochrone centered at a given point

        Args:
            orig_long: The origin longitude.
            orig_lat: The origin latitude.
            max_time: The time, in seconds via the given mode of
                transportation, that the outer edge of the isochrone will be
                generated at.
            max_distance: The distance, in meters, that the outer edge of
                the isochrone will be generated at. (BROKEN)
            mode: A key of the self.mode_map dictionary that will be remapped
                to a different string and passed to the API.

        Returns:
            A GeoJSON multipolygon.
        """

        isochrone_args = []

        if (max_distance):
            isochrone_args.append("maxWalkDistance=%d" % max_distance)

        if (max_time):
            isochrone_args.append("cutoffSec=%d" % max_time)

        if (len(isochrone_args) == 0):
            raise AssertionError("Both max_distance and max_time are None")

        url = ("http://%s/otp/routers/default/isochrone"
               "?fromPlace=%f,%f&%s&mode=%s" % (
            self.entrypoint,
            from_lat, from_long,
            "&".join(isochrone_args),
            self.map_mode(mode)
        ))

        self.log("Sending request: %s" % url)
        response = requests.get(url, timeout = self.timeout)
        data = response.content.decode()
        self.log("Response: %s" % data)

        if (response.status_code == 200):
            content = json.loads(data)
            if ("features" in content):
                geojson = content["features"][0]["geometry"]

                if (len(geojson["coordinates"]) > 0):

                    # Visualization
                    if (self.verbose):
                        base = False
                        for multipolygon in geojson["coordinates"]:
                            for polygon in multipolygon:
                                # Base polygon
                                if (base == False):
                                    self.staticmaps.add_coords(
                                        polygon,
                                        _type = "polygon",
                                        color = "0x00ff0066"
                                    )
                                    base = True
                                # Subtraction of that polygon
                                else:
                                    self.staticmaps.add_coords(
                                        polygon,
                                        _type = "polygon",
                                        color = "0xff000066"
                                    )

                        self.log("Preview with Google Static Maps API: %s"
                                 % self.staticmaps.generate_url())
                        self.staticmaps.reset()

                    return geojson
                else:
                    return False

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
        """ Routes the distance between two coordinates

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
        data = response.content.decode()
        self.log("Response: %s" % data)

        if (response.status_code == 200):
            content = json.loads(data)
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
        """ Routes the distance between two coordinates

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
        data = response.content.decode()
        self.log("Response: %s" % data)

        if (response.status_code == 200):
            content = json.loads(data)
            if (not "error" in content):
                return {
                    "distance": content["trip"]["legs"][0]["summary"]["length"] * 1000,
                    "duration": content["trip"]["legs"][0]["summary"]["time"]
                }

        return False

