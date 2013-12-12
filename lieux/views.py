# Imports from django.
from django.conf import settings
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.datastructures import MultiValueDictKeyError


# Imports from lieux.
from lieux.address import geocode_address


def google_style(request, max_results=10, db_alias=None):
    """
    A view that takes an address (from the request's querystring) and
    geocodes it, returning JSON in a structure that mimics Google's
    geocoding API.

    Takes one required and two optional arguments:
        *   request: the calling HTTP request.
        +   max_results: the number of matching address results to be
                returned. Defaults to ten results.
        +   db_alias: the name given to the geocoder's database in your
                settings.py file. Defaults to None (though a null value
                will be overridden in lines 32-37).

    Returns a JSON response containing the results of the query, ordered
    by the geocoder's confidence in how well they match the search term.
    """
    # First, check to make sure both required parameters were sent in the
    # request. If not, return an error much the same as Google does.
    try:
        request.GET['sensor']
    except MultiValueDictKeyError:
        json_response = {
            'results': [],
            'status': "REQUEST_DENIED"
        }
        return HttpResponse(
            simplejson.dumps(json_response, indent=4),
            mimetype="application/json")

    try:
        address = request.GET['address']
    except MultiValueDictKeyError:
        json_response = {
            'results': [],
            'status': "ZERO_RESULTS"
        }
        return HttpResponse(
            simplejson.dumps(json_response, indent=4),
            mimetype="application/json")

    if not db_alias:
        db_alias = getattr(
            settings,
            'GEOCODER_DB_ALIAS',
            "geocoder"
        )

    geocoded = geocode_address(
            address,
            max_results=max_results,
            db_alias=db_alias
        )

    results = []
    for geocode_result in geocoded:
        # First, compute the lat and lng of the result, and also its viewport
        # ()
        lat = geocode_result.lat
        lng = geocode_result.lng
        ne_lat = lat + .001
        ne_lng = lng + .001
        sw_lat = lat - .001
        sw_lng = lng - .001

        # Then, build up the result's JSON values, apart from the address'
        # component parts (we'll build those in the next step.
        json_result = {}
        json_result['geometry'] = {}
        json_result['geometry']['location_type'] = 'RANGE_INTERPOLATED'
        json_result['geometry']['viewport'] = {}
        json_result['geometry']['viewport']['northeast'] = {}
        json_result['geometry']['viewport']['northeast']['lat'] = ne_lat
        json_result['geometry']['viewport']['northeast']['lng'] = ne_lng
        json_result['geometry']['viewport']['southwest'] = {}
        json_result['geometry']['viewport']['southwest']['lat'] = sw_lat
        json_result['geometry']['viewport']['southwest']['lng'] = sw_lng
        json_result['geometry']['location'] = {}
        json_result['geometry']['location']['lat'] = lat
        json_result['geometry']['location']['lng'] = lng
        json_result['formatted_address'] = geocode_result.render_one_line()
        json_result['address_components'] = []
        json_result['types'] = ['street_address']

        # Now construct the address components.
        address_components = geocode_result.components

        # Attach the location's street address number to the per-address
        # values, if it has been given.
        if address_components[0] != '':
            new_component = {
                'types': ['street_number'],
                'short_name': address_components[0],
                'long_name': address_components[0],
            }
            json_result['address_components'].append(new_component)

        # Attach the street name to the per-address values, if it has been
        # given.
        if address_components[2] != '':
            address_street = [item for item in address_components[1:5] \
                                if item != '']
            new_component = {
                'types': ['route'],
                'short_name': " ".join(item for item in address_street),
                'long_name': " ".join(item for item in address_street),
            }
            json_result['address_components'].append(new_component)

        # Attach the apartment number to the per-address values, if it has been
        # given.
        if address_components[5] != '':
            new_component = {
                'types': ['subpremise'],
                'short_name': address_components[5].strip('"'),
                'long_name': address_components[5].strip('"'),
            }
            json_result['address_components'].append(new_component)

        # Attach the city name to the per-address values, if it has been given.
        if address_components[6] != '':
            new_component = {
                'types': ['locality', 'political'],
                'short_name': address_components[6],
                'long_name': address_components[6],
            }
            json_result['address_components'].append(new_component)

        # Attach the state to the per-address values, if it has been given.
        if address_components[7] != '':
            new_component = {
                'types': ['administrative_area_level_1', 'political'],
                'short_name': address_components[7],
                'long_name': address_components[7],
            }
            json_result['address_components'].append(new_component)

        # Attach the postal (ZIP) code to the per-address values, if it has
        # been given.
        if address_components[8] != '':
            new_component = {
                'types': ['postal_code'],
                'short_name': address_components[8],
                'long_name': address_components[8],
            }
            json_result['address_components'].append(new_component)

        # Add the country to the per-address values.
        new_component = {
            'types': ['country', 'political'],
            'short_name': 'US',
            'long_name': 'United States',
        }
        json_result['address_components'].append(new_component)

        # Finally, add the result we've just constructed to the list of all
        # results for this address.
        results.append(json_result)

    # Now format the per-entire-request values.
    json_response = {}
    json_response['results'] = results
    json_response['status'] = "OK"

    # Return a JSON response using simplejson and mimetype.
    return HttpResponse(
            simplejson.dumps(json_response, indent=4),
            mimetype="application/json"
        )
