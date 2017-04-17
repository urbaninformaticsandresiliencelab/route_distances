route\_distances
===============

Classes for getting the distance of a route between two places using various
different services. Included classes:

*   GoogleMapsDistances: [Google Maps Distance Matrix API](https://developers.google.com/maps/documentation/distance-matrix/intro)
*   OTPDistances: [OpenTripPlanner (OTP)](http://www.opentripplanner.org/)
*   OSRMDistances: [Open Source Routing Machine (OSRM)](http://project-osrm.org/)
*   ValhallaDistances: [Valhalla](https://mapzen.com/documentation/mobility/turn-by-turn/api-reference/)

Each class includes a distance(orig\_long, orig\_lat, dest\_long, dest\_lat)
function that returns a dictionary containing the distance of the route in the
"distance" index and the duration of the route in the "duration" index
