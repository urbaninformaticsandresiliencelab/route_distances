route_distances
===============

Classes for getting the distance of a route between two places using various
different services. Included classes:

* ``GoogleMapsDistances``: `Google Maps Distance Matrix API
  <https://developers.google.com/maps/documentation/distance-matrix/intro>`_
* ``OTPDistances``: `OpenTripPlanner (OTP) <http://www.opentripplanner.org/>`_
* ``OSRMDistances``: `Open Source Routing Machine (OSRM)
  <http://project-osrm.org/>`_
* ``ValhallaDistances``: `Valhalla
  <https://mapzen.com/documentation/mobility/turn-by-turn/api-reference/>`_

The base Distances class includes a ``distance(orig_long, orig_lat, dest_long,
dest_lat)`` function that returns a dictionary containing the distance of the
route in the ``distance`` index and the duration of the route in the
``duration`` index, or ``False`` if no route could be made.

The ``GoogleMapsDistances`` class includes built-in rate limiting that ensures
that the `Google Maps web service API limits
<https://developers.google.com/maps/premium/usage-limits#web-service-apis>`_
are not exceeded, provided that all requests made to the Google Maps Distance
Matrix API are made through a single instance of this class. The rate limiting
function is called before every request, and its parameters are defined in the
docstring of ``GoogleMapsDistances.__init__``.

Each class has a built in error handler that can either return False or throw
an exception returned by the requests library. This functionality can be
toggled by passing ``fail_fast = True`` or ``fail_fast = False`` during class
instantiation. This is useful if you want to handle exceptions on your own.
