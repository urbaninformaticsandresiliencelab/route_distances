route_distances
===============

Classes to simplify the process of getting the distance and duration of a route
between two places using various different routing services

.. code-block:: python

    import route_distances

    # api_key or client_id and client_secret are only required for the
    # GoogleMapsDistances class; the other classes require entrypoint instead.
    calculator = route_distances.GoogleMapsDistances(
        client_id = "your_client_id",
        client_secret = "your_api_key",
        fail_fast = True,
        verbose = True
    )

    orig_longlat = (-71.0913657, 42.3398186)
    dest_longlat = (-71.096354, 42.3600949)
    calculator.route(
        *orig_longlat,
        *dest_longlat,
        mode = "drive"
    )

..

::

    2017-06-02T16:00:18.492668 Sending request to Google
    2017-06-02T16:00:19.001539 Response: {'rows': [{'elements': [{'distance': {'value': 2883, 'text': '2.9 km'}, 'duration': {'value': 736, 'text': '12 mins'}, 'status': 'OK'}]}], 'origin_addresses': ['Fencourt Rd, Boston, MA 02115, USA'], 'destination_addresses': ['130 Albany St, Cambridge, MA 02139, USA'], 'status': 'OK'}
    {'distance': 2883, 'duration': 736}

..

Included classes:

* ``GoogleMapsDistances``: `Google Maps Distance Matrix API
  <https://developers.google.com/maps/documentation/distance-matrix/intro>`_
* ``OTPDistances``: `OpenTripPlanner (OTP) <http://www.opentripplanner.org/>`_
* ``OSRMDistances``: `Open Source Routing Machine (OSRM)
  <http://project-osrm.org/>`_
* ``ValhallaDistances``: `Valhalla
  <https://mapzen.com/documentation/mobility/turn-by-turn/api-reference/>`_

The base Distances class includes a ``distance(orig_long, orig_lat, dest_long,
dest_lat, mode)`` method that returns a dictionary containing the distance of
the route in the ``distance`` index and the duration of the route in the
``duration`` index, or ``False`` if no route could be made.

The ``mode`` argument is optional and is ``"walk"`` by default. You can also
specify ``"drive"``, ``"bike"``, or ``"transit"``.

The ``distance`` method has a built in error handler that can either return
False or throw an exception returned by the requests library. This
functionality can be toggled by passing ``fail_fast = True`` or ``fail_fast =
False`` during class instantiation. This is useful if you want to handle
exceptions on your own.

If you want to handle rate limiting, retrying, and exception handling entirely
on your own, you can directly use the ``route`` method for which ``distance``
is a front-end for.

Isochrone generation with the ``OTPDistances`` class
----------------------------------------------------

The OTPDistances class, in addition to calculate routes, can request isochrone
multipolygons with the ``isochrone(orig_long, orig_lat, max_time = None, 
max_distance = None, mode = "walk")`` method.  The ``orig_long``, ``orig_lat``,
and ``mode`` arguments are the same as in ``calculate``; ``max_time`` is the
difference in time from the outer edges of the isochrone to the origin point,
in seconds, and ``max_distance`` is the distance from the origin point to the
outer edges of the isochrone, in meters.

*Note:* The max_distance argument currently does nothing; `a bug has been filed
regarding this
<https://github.com/opentripplanner/OpenTripPlanner/issues/2454>`_ on the
``OpenTripPlanner`` bug tracker.

``isochrone`` returns a `GeoJSON MultiPolygon
<https://en.wikipedia.org/wiki/GeoJSON#Geometries>`_.

Example usage:

.. code-block:: python

    import route_distances
    route_distances.OTPDistances(verbose = True).isochrone(
        -71.08885, 42.34037, max_time = 600, mode = "transit"
    )

..

If ``verbose = True`` is passed to the class initialization, then the
``staticmaps.py`` script is used to generate a Google Static Maps API request
corresponding to your multipolygons. By pasting this into your browser window,
you can see what your multipolygons look like on top of Google Maps. Green
polygons are the base polygons; red polygons are inaccessible areas within the
base polygons.

Features specific to the ``GoogleMapsDistances`` class
------------------------------------------------------

The ``GoogleMapsDistances`` class can be instantiated either by supplying
``api_key`` or both ``client_id`` and ``client_secret``. The latter two
arguments are required if you want to make use of ``departure_time`` and are
only issued to Google Maps API for Work customers.

The ``GoogleMapsDistances`` class includes built-in rate limiting that ensures
that the `Google Maps web service API limits
<https://developers.google.com/maps/premium/usage-limits#web-service-apis>`_
are not exceeded, provided that all requests made to the Google Maps Distance
Matrix API are made through a single instance of this class.

The rate limiting function is called before every request and its parameters
are defined in the docstring of ``GoogleMapsDistances.__init__``. By default,
this limits you to 100k requests per 24 hours as defined by the API limits, but
you are able to configure this in the class initialization.

``GoogleMapsDistances.route`` exposes the ``departure_time`` argument of the
underlying ``googlemaps.Client.distance_matrix`` function, allowing you to get
traffic-adjusted route durations if initialized with ``client_id`` and
``client_secret``:

.. code-block:: python

    import datetime

    calculator.route(
        *orig_longlat,
        *dest_longlat,
        mode = "drive",
        departure_time = datetime.datetime(2017, 6, 7, 17)
    )

..

::

    2017-06-02T16:00:40.854631 Sending live traffic-adjusted request to Google
    2017-06-02T16:00:41.083350 Response: {'rows': [{'elements': [{'distance': {'value': 2883, 'text': '2.9 km'}, 'duration': {'value': 736, 'text': '12 mins'}, 'duration_in_traffic': {'value': 803, 'text': '13 mins'}, 'status': 'OK'}]}], 'origin_addresses': ['Fencourt Rd, Boston, MA 02115, USA'], 'destination_addresses': ['130 Albany St, Cambridge, MA 02139, USA'], 'status': 'OK'}
    {'distance': 2883, 'duration': 803}

..

Note that supplying ``departure_time`` can sometimes result in a different
distance as well, as seen above - compare this distance to the distance
obtained earlier by the first code snippet.
