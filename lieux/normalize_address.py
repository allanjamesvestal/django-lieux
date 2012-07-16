from postgis_geocoder.db_connection import submit_geocoder_query


def normalize_address(db_alias, address):
    """
    Given a database alias (as set forth in Django's settings) and an
    address to normalize, connects to that database, fires a
    normalization query and returns the resultant normalized address.

    Takes two required arguments:
        *   db_alias: the name given to the geocoder's database in your
                settings.py file.
        *   address: the address to be normalized.

    Returns a string representing the normalized address, if results
    were generated. Otherwise returns a value of None.
    """
    # First build the query.
    query = "SELECT pprint_addy(normalize_address('%s'));" % address

    # Then execute the query on our given geocoder database.
    result = submit_geocoder_query(db_alias, query)

    # Finally, return the result if there is one. Else return a value of None.
    if result == []:
        return None
    return result[0][0]
