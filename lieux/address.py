# Imports from python.
import re


# Imports fron django.
from django.conf import settings


# Imports from lieux.
from lieux.db_connection import submit_geocoder_query
from lieux.exceptions import AddressInputError, AddressNotFoundError
from lieux.objects import GeocodedAddress
from lieux.secondary_units import SECONDARY_UNITS_WITHOUT_NUMBERS
from lieux.style import DIRECTION_LOOKUPS, HIGHWAYS_TO_GEOCODER, \
    HIGHWAYS_TO_STYLE, KNOWN_STATE_ABBREVS, TEXTUAL_TO_NUMERIC_ORDINALS


# Imports from other dependencies.
from titlecase import titlecase


def format_for_geocoder(components):
    """
    A simple function that joins major address components together with
    spaces in preparation for sending to the geocoder.

    Takes one required argument:
        *   address_list: a list of strings representing the components
            of this address.

    Returns a string representing the joined values.
    """
    # Ignore the last component in the list; it will be a 't' indicating the
    # geocoder generated this result.
    components_to_geocode = components[:-1]

    # Also ignore the fifth element in the list as it's the apartment number,
    # if one was given.
    line_1_components = []

    if components_to_geocode[0] != '':
        line_1_components.append(components_to_geocode[0])

    if components_to_geocode[3].lower() in HIGHWAYS_TO_STYLE.keys() \
            and components_to_geocode[2].strip('"') != '':
        if components_to_geocode[1].strip('"') != '':
            line_1_components.append(components_to_geocode[1].strip('"'))
        line_1_components.append(components_to_geocode[3].strip('"'))
        line_1_components.append(components_to_geocode[2].strip('"'))
        if components_to_geocode[4].strip('"') != '':
            line_1_components.append(components_to_geocode[4].strip('"'))
    else:
        line_1_components = [cpnt.strip('"') for cpnt \
                in components_to_geocode[:5] if cpnt != '']
    line_1 = " ".join(cpnt.strip('"') for cpnt in line_1_components)
    line_2 = " ".join(cpnt.strip('"') for cpnt in components_to_geocode[6:] \
                                        if cpnt != '')

    return " ".join([line_1, line_2]).replace("'", "''")


def geocode_address(address, max_results=10, db_alias=None):
    """
    Given an address, approximate its physical location using the
    geocoding tool built into PostGIS v2.0.

    Takes one required and two optional arguments:
        *   address: the address to be geocoded.
        -   max_results: the number of matching address results to be
                returned. Defaults to ten results.
        -   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 33-38).

    Returns a list of lieux.objects.GeocodedAddress objects representing
    possible address-coordinate pairs and the geocoder's confidence in
    each result for the address, if results are found. Otherwise returns
    a value of None.
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

    # Normalize the address.
    normalized_address = normalize_address(
            address,
            db_alias
        )

    if not normalized_address:
        raise AddressInputError("Invalid address.")

    # If there's no state given, append the default.
    if normalized_address[7] == '':
        normalized_address[7] = getattr(
                settings,
                'DEFAULT_GEOCODER_STATE',
                'Wisconsin'
            )

    # Format the result for the geocoder.
    geocoder_formatted_address = format_for_geocoder(normalized_address)

    # Next construct the geocoding query to execute in the next step.
    geocode_query = "SELECT g.rating, ST_Y(g.geomout) As lat," \
        " ST_X(g.geomout) As lon, (addy), pprint_addy(addy) FROM" \
        " geocode('%(formatted_address)s') AS g;"

    # Finally, submit the query and return the results.
    geocode_results = submit_geocoder_query(
            geocode_query % dict(
                    formatted_address=geocoder_formatted_address
                ),
            db_alias
        )

    # Raise an appropriate error if no matching addresses were found.
    if not geocode_results:
        raise AddressNotFoundError('No address found that matches the input.')

    # Finally, create a GeocodedAddress object for each match and append it to
    # a list of all results.
    geocoded_objects = []
    for result in geocode_results:
        result_object = GeocodedAddress(
            result[0],
            result[1],
            result[2],
            result[3].strip('()').split(','))
        if normalized_address[5] != '':
            result_object.components[5] = normalized_address[5]
        geocoded_objects.append(result_object)

    # Return the first n results to the user, where n is the maximum number of
    # results we are to return.
    return geocoded_objects[:max_results]


def normalize_address(address, db_alias=None, additional_street_styles=None):
    """
    Given a database alias (as set forth in Django's settings) and an
    address to normalize, connects to that database, fires a
    normalization query and returns the resultant normalized address.

    Takes one required and one optional argument:
        *   address: the address to be normalized.
        -   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 41-46).
        -   additional_street_styles: A dict of dicts, with first-level
                keys specifying city and second-level keys specifying
                the names of streets in this city that should be changed
                before they are passed into the geocoder. The second-
                level keys will be replaced with the respective values.
                Optional, and defaults to None.

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

    # First check if the address contains a hash (which would be followed by an
    # apartment number). If so, filter this out and replace it with 'apt.'
    pound_re = re.compile(r'#')
    unit_number = None
    if pound_re.search(address) != None:
        unit_number = address.split('#')[1].split(' ')[0].strip(",")
        if not unit_number.isdigit():
            if unit_number.lower() in SECONDARY_UNITS_WITHOUT_NUMBERS.keys():
                new_address_parts = [
                    address[:pound_re.search(address).start() - 1],
                    SECONDARY_UNITS_WITHOUT_NUMBERS[unit_number.lower()],
                    address[pound_re.search(address).end() +
                            len(unit_number) + 1:]
                ]
                address = " ".join(item for item in new_address_parts)
            else:
                address = pound_re.sub('Apt. ', address)
        else:
            address = pound_re.sub('Apt. ', address)

    # Remove all punctuation from the raw address string.
    address = address.replace(',', '').replace('.', '').replace("'", "''")

    # Now build the query.
    query = "SELECT normalize_address('%(address)s');"

    # Then execute the query on our given geocoder database. Split our result
    # into a list of address components.
    result = submit_geocoder_query(
            query % dict(
                    address=address
                ),
            db_alias
        )
    result_components = result[0][0].strip('()').split(',')

    # Now, concatenate and return the result if there is one. Else return a
    # value of None.
    if [i for i in result_components[:-1] if i.replace('"', '') != ''] == []:
        return None

    result_components = [
        component.replace('"', '').replace("''", "'") for component
        in result_components
    ]

    # Now we check to see if there was a non-numeric apartment number the
    # normalizer truncated from our address. If so, append three zeroes before
    # this number and return that to the calling function.
    if result_components[5] != '':
        if result_components[6] != '' and result_components[7] != '':
            # First check if the first word in the city name is a number. If so
            # it was misappropriated from the apartment number. Take it back.
            if result_components[6].split(' ')[0].isdigit():
                result_components[6] = " ".join(
                        result_components[6].split(' ')[1:]
                    )
            # Capture the unique unit number
            unit_number = address.upper().split(
                    result_components[6].upper()
                )[0].strip().split(' ')[-1]
            # If the unit number's not already in the apartment number
            # address component, place it in there.
            if (' ' + unit_number) not in result_components[5]:
                result_components[5] = " ".join([
                        result_components[5],
                        unit_number
                    ])
        # If there is a postal code but no state, handle things slightly
        # differently.
        elif result_components[8] != '':
            result_components[5] = " ".join([
                    result_components[5],
                    result_components[6].split(' ')[0]
                ])
            result_components[6] = " ".join(
                    result_components[6].split(' ')[1:]
                )

        # If the PostGIS geocoder didn't recognize a street name, retrieve it
        # ourselves from the original address.
        if result_components[2] == '':
            result_components[2] = " ".join(address.split(
                    result_components[0])[1].split(
                            result_components[5]
                        )[:-1]
                ).strip(' ')

    # Next see if the geocoder misread a non-USPS standard state abbreviation
    # as part of the city name. If there's no state specified and a Django-
    # recognized state abbreviation comprises the last (but not the only) part
    # of the city value, remove it and use it as the state.
    if result_components[7] == '':
        city_to_compare = result_components[6].strip().replace(',',
                '').replace('.', '').lower()
        for state_abbrev in KNOWN_STATE_ABBREVS.keys():
            abbrev_regex = re.compile(r'(^|\W)%s' % state_abbrev.lower())
            if abbrev_regex.search(city_to_compare) and city_to_compare.split(
                                    ' %s' % state_abbrev.lower())[-1] == '':
                result_components[6] = titlecase(state_abbrev.join(
                        city_to_compare.split(' %s' % state_abbrev)[:-1]
                    ))
                result_components[7] = KNOWN_STATE_ABBREVS[state_abbrev]

    # Alternately, if the value for street name ends in a known state
    # abbreviation and there's no state, normalize the state to its USPS code
    # and re-run normalization.
    if result_components[6] == '' and result_components[7] == '':
        street_to_compare = result_components[2].strip().replace(',',
                '').replace('.', '').lower()
        for state_abbrev in KNOWN_STATE_ABBREVS.keys():
            if ' %s' % state_abbrev in street_to_compare and \
                    street_to_compare.split(' %s' % state_abbrev)[-1] == '':
                new_state = KNOWN_STATE_ABBREVS[state_abbrev]
                revised_address = " ".join([
                        format_for_geocoder(result_components).lower().split(
                                                    ' %s' % state_abbrev)[0],
                        new_state
                    ])
                # RECURSION RECURSION RECURSION: Call normalize_address
                # function for the revised address. Note that if the
                # USPS-abbreviated value for the selected key in
                # known_state_abbrevs isn't among the states PostGIS knows of
                # this will cause infinite recursion. Which is bad.)
                result_components = normalize_address(
                        revised_address,
                        db_alias
                    )
                result_components[2] = titlecase(result_components[2])
                result_components[6] = titlecase(result_components[6])

    # Now check to see if this address is on a state, federal or interstate
    # highway. If it is, it may not have been recognized by the geocoder and
    # may be listed as part of the street name (not the stret type). If so,
    # fix the address components.
    if result_components[3] == '':
        highway_regex = re.compile(r'%s' % "|".join([
                '^%s(\d+|\w+)' % item
                    for item in HIGHWAYS_TO_GEOCODER.keys()
            ]))
        # First see if the address begins with one of our non-standard highway
        # types. If so, split into road number/letter and road type based on
        # the matching key.
        highway_match = highway_regex.search(result_components[2].lower())
        if highway_match:
            highway_keys_regex = re.compile(r'%s' % "|".join([
                    '^%s' % item for item in HIGHWAYS_TO_GEOCODER.keys()
                ]))
            highway_key_match = highway_keys_regex.search(highway_match.string)
            result_components[3] = HIGHWAYS_TO_GEOCODER[
                    highway_key_match.group().lower()
                ]
            result_components[2] = highway_match.string[
                    highway_key_match.end():highway_match.end()
                ].strip().upper()
            # Now see if a post-direction was specified. If so split this off
            # and place it in the correct position in the components list.
            if len(highway_match.string) > highway_match.end():
                result_components[4] = highway_match.string[
                        highway_match.end():
                    ].strip().upper()
            # Finally, check if the city was mistakenly placed into the
            # postdirectional position and correct this as needed.
            if result_components[4] != '' and result_components[6] == '':
                directions_re = re.compile(r'%s' % "|".join([
                    '^%s' % item for item in DIRECTION_LOOKUPS.keys()
                    ]))
                direction_search = directions_re.search(result_components[4])
                if direction_search and \
                        len(direction_search.string) > direction_search.end():
                    result_components[6] = titlecase(result_components[4][
                            direction_search.end():
                        ]).strip()
                    result_components[4] = result_components[4][
                            :direction_search.end()
                        ].upper().strip()
                elif not direction_search:
                    result_components[6] = titlecase(
                            result_components[4]
                        ).strip()
                    result_components[4] = ''

    # If we still don't have a state specified, use the system default.
    if result_components[7] == '':
        result_components[7] = getattr(
                settings,
                'DEFAULT_GEOCODER_STATE',
                'Wisconsin'
            )

    if result_components[2].lower() \
            in TEXTUAL_TO_NUMERIC_ORDINALS.keys():
        result_components[2] = TEXTUAL_TO_NUMERIC_ORDINALS[
                                result_components[2].lower()]

    # Finally see if the street is a common misspelling (or an alternate
    # spelling) we can correct. Note that for this we use a dictionary of
    # dictionaries for streets -- the outer dictionary's keys are city names,
    # within which are keys for individual street spellings, which then map to
    # their proper, geo-codable names.
    if additional_street_styles:
        if result_components[6].lower() in additional_street_styles.keys() \
                and result_components[2].lower() in \
                additional_street_styles[
                        result_components[6].lower()
                    ].keys():
            result_components[2] = additional_street_styles[
                                    result_components[6].lower()
                                ][result_components[2].lower()]

    return result_components
