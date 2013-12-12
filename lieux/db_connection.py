# Imports from django.
from django.conf import settings
from django.db import connections


def submit_geocoder_query(query, db_alias=None):
    """
    Given a database alias (as set forth in Django's settings) and a
    query to run, connects to that database, fires the given query and
    returns all results.

    Takes one required and one optional argument:
        *   query: the actual query to run.
        -   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 240-245).

    Returns a list of tuples representing each line of results and its
    respective columns, if there are results generated. Otherwise
    returns a value of None.
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

    # First, build the cursor that will connect us to the database.
    cursor = connections[db_alias].cursor()

    # Then submit the query and get all resulting rows.
    cursor.execute(query)
    result = cursor.fetchall()

    # If there were no results, return a value of None. Otherwise, send back
    # the results.
    if result == []:
        return None
    return result
