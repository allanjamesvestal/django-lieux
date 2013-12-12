# Imports fron django.
from django.conf import settings


# Imports from lieux.
from lieux import ap_style
from lieux.address import normalize_address
from lieux.latstatestyle import CROSSWALK
from lieux.secondary_units import SECONDARY_UNITS_WITH_NUMBERS
from lieux.street_suffixes import street_suffixes
from lieux.style import HIGHWAYS_STATE_APPEND, HIGHWAYS_TO_STYLE


# Imports from other dependencies.
from titlecase import titlecase


def format_for_styler(components):
    """
    A simple function that joins all address components together with
    spaces in preparation for sending to the styler function.

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

    address_line = None
    if components_to_geocode[5] != '':
        address_line = components_to_geocode[5].replace('"', '').strip()

    line_2_components = [cpnt.strip('"') for cpnt in components_to_geocode[6:] \
                                        if cpnt != '']

    # If there is a city name specified, make sure it's in titlecase.
    if components_to_geocode[6] != '':
        line_2_components[0] = '"%s"' % titlecase(line_2_components[0].lower())

    line_2 = " ".join(line_2_components)

    if address_line:
        return " ".join([line_1, address_line, line_2])

    return " ".join([line_1, line_2])


def format_result_in_ap_style(address, db_alias=None, street_custon_styles=None):
    """
    Given a string representing a street address, parses that location
    and converts it to Associated Press style. Eventually this will be
    joined by a format_result_in_usps_style function as well.

    Takes one required and two optional arguments:
        *   address: a string representing the address to be properly
                formatted. Must have either city and state or ZIP specified.
        -   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 240-245).
        -   street_custon_styles: A dict of dicts, with first-level
                keys specifying a city and second-level keys specifying
                the names of streets in this city that should be changed
                before they are returned from the formatter. The second-
                level keys will be replaced with the respective values.
                Optional, and defaults to None.

    Returns a string representing the address converted to follow style.
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

    # Remove all periods and commas from the address.
    address = address.replace(',', '').replace('.', '')

    # First, normalize this address using PostGIS.
    result_list = normalize_address(
            address,
            db_alias
        )

    formatted_address = []
    formatted_first_line = []
    # For our additional processing, check if there were non-numeric characters
    # in the street address. If so, replace their normalized value with the raw
    # street number. Else use the normalized value.
    if result_list[0] != '':
        if not address.split(' ')[0].isdigit():
            formatted_first_line.append(
                        address.split(' ')[0].strip(' ').upper()
                    )
        else:
            formatted_first_line.append(result_list[0])

    # Now check to see if the street has a predirection. If so convert its
    # value to Associated Press style.
    if result_list[1] != '':
        formatted_first_line.append(ap_style.PREDIRECTIONS_TO_AP_STYLE[
            result_list[1].lower()].upper())

    # Now remove any quotes that may have been added to the street name, and
    # see if it matches one of the streets for which we have a custom style. If
    # so, return this custom street name in lieu of the one from the geocoder.
    # Else return the geocoded result in titlecase.

    if result_list[2] != '' and result_list[3].lower() not \
                in HIGHWAYS_TO_STYLE.keys():
        if street_custon_styles:
            if result_list[6].lower() in street_custon_styles.keys() and \
                    result_list[2].strip('"').lower() in street_custon_styles[
                            result_list[6].lower()
                        ].keys():
                formatted_first_line.append(
                        street_custon_styles.STREETS_TO_STYLE[
                            result_list[6].lower()
                        ][result_list[2].strip('"').lower()])
        else:
            formatted_first_line.append(titlecase(
                result_list[2].strip('"')
            ))

    # Next match roads to their corrrect abbreviations (or non-abbreviations)
    # according to Associated Press style.
    formatted_highway = None
    if result_list[3] != '':
        if result_list[3].lower() in street_suffixes.keys() and \
                        street_suffixes[result_list[3].lower()] \
                        in ap_style.SUFFIXES_TO_AP_STYLE.keys():
            formatted_first_line.append(
                    ap_style.SUFFIXES_TO_AP_STYLE[
                            street_suffixes[result_list[3].lower()]
                        ].capitalize()
                )
        elif result_list[3].lower() in HIGHWAYS_TO_STYLE.keys():
            if result_list[3].lower() in HIGHWAYS_STATE_APPEND:
                if result_list[2] != '':
                    formatted_first_line.append("%s%s" % (
                            "%(state_full)s %(hwy_fmt)s",
                            result_list[2].strip('"').upper()
                        ))
                    formatted_highway = " ".join(HIGHWAYS_TO_STYLE[
                            result_list[3].lower()
                        ].split(' ')[1:])
                else:
                    formatted_first_line.append("%(state_full)s %(hwy_fmt)s")
                    formatted_highway = HIGHWAYS_TO_STYLE[
                            result_list[3].lower()
                        ]
            else:
                if result_list[2] != '':
                    formatted_first_line.append('%s%s' % (
                            HIGHWAYS_TO_STYLE[result_list[3].lower()],
                            result_list[2].strip('"').upper()
                        ))
                else:
                    formatted_first_line.append(
                            HIGHWAYS_TO_STYLE[result_list[3].lower()]
                        )

    # Now append the post-directional suffix, if one exists. Not sure about the
    # style guidelines on this, so I'll defer doing anything too fancy until I
    # know for sure. ~AJV
    if result_list[4] != '':
        formatted_first_line.append(result_list[4])

    # Now append the entire first line of the address to an array of the whole
    # address by line.
    formatted_address.append(" ".join(item for item in formatted_first_line))

    # Next process the unit number (if one was given).
    if result_list[5] != '':
        unit_raw = result_list[5]
        unit_kind = unit_raw.split(' ')[0].lower()
        if unit_kind.replace('.', '') in SECONDARY_UNITS_WITH_NUMBERS.keys():
            unit_type = SECONDARY_UNITS_WITH_NUMBERS[unit_kind.replace('.',
                    '')]
            unit_remainder = unit_raw[len(unit_kind):].upper()
            if unit_remainder[1:4] == '000':
                unit_remainder = ' %s' % unit_remainder[4:]
            #
            if len(result_list[5].split(' ')) == 2 and \
                    result_list[5].split(' ')[0].upper() == \
                    result_list[5].split(' ')[1].upper():
                unit_formatted = [
                    unit_type.capitalize(),
                    ' unit'
                ]
            else:
                unit_formatted = [
                    unit_type.capitalize(),
                    unit_remainder
                ]
            formatted_address.append("".join(item for item in unit_formatted))
        else:
            pass

    # Now format the last line of the address (we won't make a fourth line for
    # country), complete with the city, state and ZIP code (if given).
    formatted_city_state_line = []

    # If the address has a city name listed, check if it's listed as a style
    # exception to the normal rules. If so return it in the local style; if not
    # capitalize each word of it and return that.
    if result_list[6] != '':
        formatted_city_state_line.append(titlecase(result_list[6]) + ",")

    # If the address has a state listed, look for it first in the abbreviations
    # to state names in Associated Press style crosswalk. If the abbreviation
    # is not there, uppercase it as given and return it instead.
    if result_list[7] != '':
        if result_list[7].lower() in CROSSWALK.keys():
            state_match = CROSSWALK[result_list[7]]
            formatted_city_state_line.append(state_match['ap'])
            state_full = state_match['name']
        else:
            formatted_city_state_line.append(result_list[7].upper())
            state_full = result_list[7].upper()

    # If the address has a ZIP code, add that to the formatted line.
    if result_list[8] != '':
        formatted_city_state_line.append(result_list[8])

    # Concatenate the last line of the address and append it to the
    # formatted_address array.
    formatted_address.append(" ".join(
            item for item in formatted_city_state_line
        ))

    if formatted_highway:
        highway_info = {
            'hwy_fmt': formatted_highway,
            'state_full': state_full,
        }
        formatted_address[0] = formatted_address[0] % highway_info

    return formatted_address
