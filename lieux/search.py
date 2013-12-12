# Imports from django.
from django.conf import settings


# Imports from lieux.
from lieux.exceptions import AddressNotFoundError, IntersectionInputError, \
    IntersectionNotFoundError, NoResultsError
from lieux.address import geocode_address
from lieux.intersection import geocode_intersection, \
    ALWAYS_DENOTES_INTERSECTION_RE, SOMETIMES_DENOTES_INTERSECTION_RE
from lieux.style import STREET_NUMBERS_TO_ORDINALS


def search(search_string, max_results=10, db_alias=None):
    """
    Given a search string, attempts to find matching addresses or
    intersections based on input format. (Eventually, this will attempt
    to find matching points of interest as well.)

    Takes one required and one optional argument:
        *   search_string: the address or intersection, as a string,
                to be geocoded.
        +   max_results: the maximum number of results to be returned
                for any search. Defaults to ten results.
        +   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 47-52).

    Returns a list of lieux.objects.GeocodedIntersection objects or
    lieux.objects.GeocodedAddress objects representing possible
    intersection- or address-coordinate pairs and the geocoder's
    confidence each result matches the query, if results are found.
    Otherwise returns a value of None.
    """
    # Before anything else, SQL-escape the address by removing any single and
    # double quotes from the raw string. This may screw with some obscure
    # addresses that have apostrophes; we'll have to see if it does.
    search_string = search_string.replace("'", "").replace('"', '')

    # Unless otherwise specified, the database alias will be that which has
    # been specified in settings.GEOCODER_DB_ALIAS (or, failing that, the
    # string 'geocoder').
    if not db_alias:
        db_alias = getattr(
                settings,
                'GEOCODER_DB_ALIAS',
                'geocoder'
            )

    # Search for a match. If the address string includes an '@' symbol, look no
    # further and start processing the input as an intersection. Else if the
    # string has a match for one of the other union symbols, parse to see if it
    # is an address (whether it begins with a number). Note that we want to
    # protect against ordinal streets ('1st', '58th', etc. setting off this
    # filter condition), so we'll screen to see if the first word is an ordinal
    # first.
    certain_match = ALWAYS_DENOTES_INTERSECTION_RE.search(
            search_string.upper()
        )
    possible_match = SOMETIMES_DENOTES_INTERSECTION_RE.search(
            search_string.upper()
        )

    results = None
    if certain_match:
        results = geocode_intersection(
                search_string,
                max_results=max_results,
                db_alias=db_alias
            )
    elif possible_match:
        if search_string.split(' ')[0][0].isdigit():
            if search_string.split(' ')[0] \
                            in STREET_NUMBERS_TO_ORDINALS.values():
                try:
                    results = geocode_intersection(
                            search_string,
                            max_results=max_results,
                            db_alias=db_alias
                        )
                except IntersectionInputError:
                    pass
                except IntersectionNotFoundError:
                    pass
            else:
                pass
        else:
            try:
                results = geocode_intersection(
                        search_string,
                        max_results=max_results,
                        db_alias=db_alias
                    )
            except IntersectionInputError:
                pass
            except IntersectionNotFoundError:
                pass

    if not results:
        try:
            results = geocode_address(
                    search_string,
                    max_results=max_results,
                    db_alias=db_alias
                )
        except AddressNotFoundError:
            raise NoResultsError("No matching addresses or intersections " \
                                "were found based on your search.")

    return results
