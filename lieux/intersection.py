# Imports from python.
import re


# Imports from django.
from django.conf import settings


# Imports from lieux.
from lieux.address import normalize_address
from lieux.db_connection import submit_geocoder_query
from lieux.exceptions import IntersectionInputError, IntersectionNotFoundError
from lieux.objects import GeocodedAddress, GeocodedIntersection
from lieux.us_states import US_STATES


# Build the necessary regexes.
ALWAYS_DENOTES_INTERSECTION_RE = re.compile(r'\s*@\s*')
SOMETIMES_DENOTES_INTERSECTION_RE = re.compile(
    r'\s+AND\s+|\s+AT\s+|\s*&\s*|\s*/\s*')


def geocode_intersection(intersection_raw, max_results=10, db_alias=None):
    """
    Given a string representing the intersection of two streets,
    approximate the physical location of that intersection using the
    geocoding tool built into PostGIS v2.0.

    Takes one required and two optional arguments:
        *   intersection_raw: the intersection to be geocoded, in string
                form.
        -   max_results: the number of matching address results to be
                returned. Defaults to ten results.
        -   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 32-37).

    Returns a list of lieux.objects.GeocodedIntersection objects
    representing possible address-coordinate pairs and the geocoder's
    confidence in each result for the address, if results are found.
    Otherwise returns a value of None.
    """
    # Unless otherwise specified, the database alias will be that which has
    # been specified in settings.GEOCODER_DB_ALIAS (or, failing that, the
    # string 'geocoder').
    if not db_alias:
        db_alias = getattr(
                settings,
                'GEOCODER_DB_ALIAS',
                'geocoder'
            )

    # First, normalize the intersection.
    intersection_dict = normalize_intersection(
            intersection_raw,
            db_alias
        )

    # Build and execute the query.
    query_args = [
        "'%s'" % intersection_dict['first_road'],
        "'%s'" % intersection_dict['second_road'],
        "'%s'" % intersection_dict['state']
    ]
    reverse_query_args = [
        "'%s'" % intersection_dict['second_road'],
        "'%s'" % intersection_dict['first_road'],
        "'%s'" % intersection_dict['state']
    ]

    geocoding_query = "SELECT g.rating, ST_Y(g.geomout), ST_X(g.geomout), " \
                    "addy FROM geocode_intersection(%(query_string)s) AS g;"

    # If we have both a city and a ZIP code, try and run the query with both.
    # If we don't, or if that query fails, try with just the city (if we have
    # it). Failing that, try with just a ZIP code, and as a last resort try
    # using just the state (which will take the longest to proces and has the
    # highest likelihood of yielding bunk results).
    intersection_result = None
    if intersection_dict['city'] and intersection_dict['zip']:
        this_query = []
        this_query.append("'%s'" % intersection_dict['city'])
        this_query.append("'%s'" % intersection_dict['zip'])
        this_query.append(str(max_results * 5))
        # Run the forward query (street one at street two, in the order the
        # user entered it).
        intersection_result = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join(query_args + this_query)
                    ),
                db_alias
            )
        # Then run the backward query (street two at street one, in the reverse
        # order from how the user entered it).
        cross_street_intersection = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join(reverse_query_args + this_query)
                    ),
                db_alias
            )

    if intersection_dict['city'] and not intersection_result:
        this_query = []
        this_query.append("'%s'" % intersection_dict['city'])
        this_query.append("''")
        this_query.append(str(max_results * 5))
        # Run the forward query (street one at street two, in the order the
        # user entered it).
        intersection_result = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join(query_args + this_query)
                    ),
                db_alias
            )

        # Then run the backward query (street two at street one, in the reverse
        # order from how the user entered it).
        cross_street_intersection = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join(reverse_query_args + this_query)
                    ),
                db_alias
            )

    if intersection_dict['zip'] and not intersection_result:
        this_query = []
        this_query.append("''")
        this_query.append("'%s'" % intersection_dict['zip'])
        this_query.append(str(max_results * 5))
        # Run the forward query (street one at street two, in the order the
        # user entered it).
        intersection_result = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join(query_args + this_query)
                    ),
                db_alias
            )
        # Then run the backward query (street two at street one, in the reverse
        # order from how the user entered it).
        cross_street_intersection = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join(reverse_query_args + this_query)
                    ),
                db_alias
            )

    if not intersection_result:
        this_query = []
        this_query.append("''")
        this_query.append("''")
        this_query.append(str(max_results * 5))
        # Run the forward query (street one at street two, in the order the
        # user entered it).
        intersection_result = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join(query_args + this_query)
                    ),
                db_alias
            )
        # Then run the backward query (street two at street one, in the reverse
        # order from how the user entered it).
        cross_street_intersection = submit_geocoder_query(
                geocoding_query % dict(
                        query_string=", ".join([
                                query_args[1],
                                query_args[0],
                                query_args[2]
                            ] + this_query)
                    ),
                db_alias
            )

    # If the geocoder couldn't find the intersection, throw an exception.
    if not intersection_result:
        raise IntersectionNotFoundError("No intersection of those streets " \
            "was found for any combination of state and city and/or ZIP code "\
            "provided.")

    # Otherwise, create several python objects -- one for each intersection
    # result returned, and one for the address tied to each result.

    # We'll need to filter, though, so we don't get multiple results for the
    # same corner. We do this by seeing if a result has the exact same
    # coordinates and is on the same street as a recorded address and, if it is
    # and does, excluding that result.
    resultant_addresses = []
    for result in intersection_result:
        address = GeocodedAddress(
                result[0],
                result[1],
                result[2],
                result[3].strip('()').split(',')
            )
        # Create the 'comparator' dict, which we'll use to find near-duplicate
        # address results.
        comparator = {}
        for result in resultant_addresses:
            comparator[
                    '%s,%s' % (result.lat, result.lng)
                ] = [
                " ".join(
                        [cpnt for cpnt in result.components[1:5]
                                if cpnt.replace('"', '') != '']
                    )
                ]
        # Now format this particular result's street in the same manner as the
        # comparator values above.
        address_street_formatted = " ".join([
                cpnt for cpnt in address.components[1:5]
                if cpnt.replace('"', '') != ''
            ])
        # If the result's coordinates are a key in the comparator, see if their
        # value is on the same exact street (with directionals and type) as the
        # existing value. If not, add this result to our filtered results list.
        if '%s,%s' % (address.lat, address.lng) in comparator.keys():
            if comparator['%s,%s' % (address.lat,
                        address.lng)][0] == address_street_formatted:
                pass
            else:
                resultant_addresses.append(address)
        else:
            resultant_addresses.append(address)

    # We'll build the list of cross-streets at intersections the same way, and
    # then pipe these into a dict with the coordinates as key.
    cross_street_addresses = {}
    if cross_street_intersection:
        for result in cross_street_intersection:
            # Initialize a GeocodedAddress object for cross-street address at the
            # given intersections.
            address = GeocodedAddress(
                    result[0],
                    result[1],
                    result[2],
                    result[3].strip('()').split(',')
                )
            # Create the 'comparator' dict, which we'll use to find near-duplicate
            # address results.
            cross_street_addresses[
                    '%s,%s' % (address.lat, address.lng)
                ] = " ".join(
                        [cpnt for cpnt in address.components[1:5]
                                if cpnt.replace('"', '') != '']
                    )

    # Finally, loop through all forward-query intersection results, matching
    # each with its reverse-query intersection (if one exists) and defining it
    # as a GeocodedIntersection object.
    result_objects = []
    for address in resultant_addresses:
        street_one = " ".join([
                cpnt for cpnt in address.components[1:5] if cpnt != ''
            ])

        # If the intersection has a corresponding reverse-query address (with
        # the same lat and lng), use that as street_two. Otherwise grab the
        # value from the original intersection string.
        if '%s,%s' % (address.lat, address.lng) \
                    in cross_street_addresses.keys():
            street_two = cross_street_addresses['%s,%s' % (
                    address.lat,
                    address.lng
                )]
        else:
            street_two = intersection_dict['second_road']

        intersection_obj = GeocodedIntersection(
                address.rating,
                street_one,
                street_two,
                address
            )
        result_objects.append(intersection_obj)

    # Return the first n results to the user, where n is the maximum number of
    # results we are to return.
    return result_objects[:max_results]


def normalize_intersection(intersection_raw, db_alias=None):
    """
    Given a database alias (as set forth in Django's settings) and an
    intersection (as a string) to normalize, connects to that database,
    fires a normalization query and returns the resultant normalized
    address.

    Takes one required and one optional argument:
        *   intersection_raw: the address to be normalized.
        -   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 39-44).

    Returns a string representing the normalized address, if results
    were generated. Otherwise returns a value of None.
    """
    # Unless otherwise specified, the database alias will be that which has
    # been specified in settings.GEOCODER_DB_ALIAS (or, failing that, the
    # string 'geocoder').
    if not db_alias:
        db_alias = getattr(
                settings,
                'GEOCODER_DB_ALIAS',
                'geocoder'
            )

    # Find the match. If the intersection string includes an '@' symbol, look
    # no further and start processing the input as an intersection. Else if the
    # string has a match for one of the other union symbols, parse to find
    # where one road ends and the other begins.
    certain_match = ALWAYS_DENOTES_INTERSECTION_RE.search(
            intersection_raw.upper()
        )
    possible_match = SOMETIMES_DENOTES_INTERSECTION_RE.search(
            intersection_raw.upper()
        )

    # Split the first road and the rest of the address according to whether
    # there was a sure match or only a possible one.
    # If there wasn't any match at all raise an input error.
    if certain_match:
        first_road = intersection_raw[:certain_match.start()].strip(' ')
        remainder = intersection_raw[certain_match.end():].strip(' ')
    elif possible_match:
        first_road = intersection_raw[:possible_match.start()].strip(' ')
        remainder = intersection_raw[possible_match.end():].strip(' ')
    else:
        raise IntersectionInputError("Missing second address to be parsed.")

    # Now we have to separate the second street from city, state and ZIP code
    # information (if any of this was supplied at all). The best way to do this
    # is to attach a fake street address number and run this through PostGIS'
    # normalize_address function.
    spoofed_street_address = " ".join([
            "1217",
            remainder
        ])
    parsable = normalize_address(
            spoofed_street_address,
            db_alias
        )

    # Everything hinges on the state. So if there was a state specified to the
    # normalizer (and if it's a legitimate American state), proceed to build
    # the rest of the query according to that information. If not, add the
    # default state (WI in our case) into the data.
    address_components = {
        'city': None,
        'state': None,
        'zip': None
    }
    if parsable:
        # Before processing the parsed result, remove all quotes from each
        # address component.
        parsable = [item.replace('"', '') for item in parsable]
        if parsable[7] and parsable[7] in [item[0] for item in US_STATES]:
            address_components['state'] = parsable[7]
        else:
            address_components['state'] = getattr(
                        settings,
                        'DEFAULT_GEOCODER_STATE',
                        'Wisconsin'
                    )

        # If there was a ZIP code specified, add that to the address components
        # list too.
        if parsable[8]:
            address_components['zip'] = parsable[8]

        # Finally, if there was a city specified add that to the address
        # components as well.
        if parsable[6]:
            address_components['city'] = parsable[6]

        second_road = " ".join([part for part in parsable[1:5] if part != ''])

        # Now we'll go back and normalize the first street name the same way.
        spoofed_first = " ".join([
                "1217",
                first_road,
                'Milwaukee',  # Note: it doesn't matter the city & state we use.
                'WI'  # The function just needs something in these spots.
            ])
        first_road_parsable = normalize_address(
                spoofed_first,
                db_alias
            )
        if first_road_parsable:
            first_road = " ".join([part for part in first_road_parsable[1:5] \
                                    if part != ''])
            if first_road == '':
                raise IntersectionInputError('Invalid first road value.')
        else:
            raise IntersectionInputError('Invalid first road value.')

        address_components['first_road'] = first_road
        address_components['second_road'] = second_road

        return address_components

    else:
        raise IntersectionInputError('Invalid second road or city/state/ZIP ' \
                                    'value.')
