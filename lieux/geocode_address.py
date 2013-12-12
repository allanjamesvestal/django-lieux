from lieux.db_connection import submit_geocoder_query
from lieux.normalize_address import normalize_address


def geocode_address(db_alias, address):
    """
    Given an address, approximate its physical location using the
    geocoding tool built into PostGIS v2.0.

    Takes two required arguments:
        *   db_alias: the name given to the geocoder's database in your
                settings.py file.
        *   address: the address to be geocoded.

    Returns a list of tuples representing possible address-coordinate
    pairs and the geocoder's confidence in each result for the address,
    if results are found. Otherwise returns a value of None.
    """
    # First normalize the address.
    normalized_address = normalize_address(db_alias, address)

    # Next construct the geocoding query to execute in the next step.
    geocode_query = "SELECT g.rating, ST_Y(g.geomout) As lat," \
        " ST_X(g.geomout) As lon, (addy), pprint_addy(addy) FROM" \
        " geocode('%s') AS g;" % (normalized_address)

    # Finally, submit the query and return the results.
    geocode_results = submit_geocoder_query(db_alias, geocode_query)

    return geocode_results
