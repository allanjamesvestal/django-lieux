class GeocodedAddress(object):
    """
    A class that describes a geocoded address.

    Has the following components:
        ~   rating: the geocoder's confidence that this result matches
                the user's query.
        ~   lat: the latitude of the address.
        ~   lng: the longitude of the address.
        ~   components: the pieces of the address, represented as a list
                with the same spacing as PostGIS' (addy) object.

    Includes methods __init__(), __repr__() and __unicode__() for
    self-reference, format_in_ap_style(), render_coords(),
    render_one_line() and render_multi_line() for conversion to style
    and as_wkt() and coords() to enable quick formatting.
    """
    def __init__(self, rating, lat, lng, components):
        self.rating = rating
        self.lat = lat
        self.lng = lng
        self.components = components

    def __repr__(self):
        return '<Address: %s>' % self.__unicode__()

    def __unicode__(self):
        return '%s %s' % (
                self.render_one_line(),
                self.render_coords()
            )

    def format_in_ap_style(self):
        # Imports from lieux
        from lieux.formats import format_for_styler, format_result_in_ap_style
        return format_result_in_ap_style(
                format_for_styler(self.components)
            )

    def render_coords(self):
        return "(%s, %s)" % (self.lat, self.lng)

    def render_one_line(self):
        return ", ".join([ln for ln in self.format_in_ap_style() if ln != ''])

    def render_multi_line(self):
        return "\n".join([ln for ln in self.format_in_ap_style() if ln != ''])

    def as_wkt(self):
        return 'POINT(%s %s)' % (
                self.lng,
                self.lat
            )

    def coords(self):
        return [self.lat, self.lng]


class GeocodedIntersection(object):
    """
    A class that describes a geocoded intersection.

    Has the following components:
        ~   rating: the geocoder's confidence that this result matches
                the user's query.
        ~   street_one: the primary street at this intersection (as
                determined by which came first in the query).
                Represented as a string with the street name in
                Associated Press style.
        ~   street_two: the secondary street at this intersection (as
                determined by which came last in the query). Represented
                as a string with the street name in Associated Press
                style.
        ~   address: a GeocodedAddress object representing the address
                of this intersection.

    Includes methods __init__(), __repr__() and __unicode__() for
    self-reference, format_in_ap_style(), render_one_line() and
    render_multi_line() for conversion to style and as_wkt() and
    coords() to enable quick formatting.
    """
    def __init__(self, rating, street_one, street_two, address):
        self.rating = rating
        self.street_one = street_one
        self.street_two = street_two
        self.address = address

    def __repr__(self):
        return '<Intersection: %s>' % self.__unicode__()

    def __unicode__(self):
        return '%s %s' % (
                self.render_one_line(),
                self.address.render_coords()
            )

    def format_in_ap_style(self):
        # Imports from lieux
        from lieux.formats import format_result_in_ap_style
        first_street_formatted = format_result_in_ap_style(
                '1217 %s, Milwaukee, WI' % self.street_one
            )
        fmt_string = [
            " ".join([
                    first_street_formatted[0][5:],
                    'at',
                    format_result_in_ap_style(
                            '1217 %s, Milwaukee, WI' % self.street_two
                        )[0][5:]
                ]),
            first_street_formatted[1]
        ]
        return fmt_string

    def render_one_line(self):
        return ", ".join([ln for ln in self.format_in_ap_style() if ln != ''])

    def render_multi_line(self):
        return "\n".join([ln for ln in self.format_in_ap_style() if ln != ''])

    def as_wkt(self):
        return self.address.as_wkt()

    def coords(self):
        return [
                self.address.lat,
                self.address.lng
            ]
