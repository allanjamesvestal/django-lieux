from django.db import connections


def submit_geocoder_query(db_alias, query):
    """
    Given a database alias (as set forth in Django's settings) and a
    query to run, connects to that database, fires the given query and
    returns all results.

    Takes two required arguments:
        *   db_alias: the name given to the geocoder's database in your
                settings.py file.
        *   query: the actual query to run.

    Returns a list of tuples representing each line of results and its
    respective columns, if there are results generated. Otherwise
    returns a value of None.
    """
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
