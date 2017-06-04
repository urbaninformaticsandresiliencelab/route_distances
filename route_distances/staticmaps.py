#!/usr/bin/env python3
# Small library for generating URLs of visualizations

class Constructor(object):
    """ Constructs Google Static Maps API URLs

    Constructs requests for the Google Static Maps API by storing substrings of
    the overall URL which are created by the add_coords function. The
    generate_url function returns the full, assembled URL.

    Attributes:
        parameters: A an array of strings, each of which is an additional
            parameter that will be appended to the base Static Maps API request
            URL.
    """

    def __init__(self):
        self.parameters = []

    def generate_url(self, size = "400x400"):
        """ Combine stored shapes into a single URL

        Joins the base url with shapes specified by the user with an ampersand
        in between.

        Args:
            size: The size of the image to be generated.

        Returns:
            A string of the API request's URL
        """
        return "&".join(["https://maps.googleapis.com/maps/api/staticmap?size=%s" % size] + self.parameters)

    def add_coords(self, new_coords, _type = "markers", color = "0x00ff0066"):
        """ Add coordinates to the current static map

        Adds a string to the parameters table containing a list of coordinates
        and variables describing how they should be drawn.

        Args:
            new_coords: A multidimensional array containing (longitude,
                latitude) pairs of coordinates.
            _type: A string describing what kind of visual will be drawn.
                Possible options include: markers, path, polygon.
            color: A string containing a 24-bit or 32-bit hex value that
                corresponds to the desired color.
        """

        if (_type == "markers"):
            new_parameters = "markers=color:%s|size:tiny" % color
        elif (_type == "path"):
            new_parameters = "path=color:%s|weight:5" % color
        elif (_type == "polygon"):
            new_parameters = "path=color:0x00000000|fillcolor:%s|weight:5" % color

        for coord in new_coords:
            new_parameters += "|%f,%f" % (coord[1], coord[0])

        self.parameters.append(new_parameters)

    def reset(self):
        """ Clears all stored paramters """
        self.parameters = []
