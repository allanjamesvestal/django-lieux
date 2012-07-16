# Imports from django.
from django.conf import settings
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.datastructures import MultiValueDictKeyError

# Imports from postgis_geocoder.
from postgis_geocoder.geocode_address import geocode_address


def google_style(request):
    """
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

    db_alias = getattr(settings, 'GEOCODER_ALIAS', "geocodder")

    geocoded = geocode_address(db_alias, address)

    results = []
    for geocode_result in geocoded:
        # First, compute the lat and lng of the result, and also its viewport
        # ()
        lat = geocode_result[1]
        lng = geocode_result[2]
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
        json_result['formatted_address'] = geocode_result[4]
        json_result['address_components'] = []
        json_result['types'] = ['street_address']

        # Now construct the address components.
        address_components = geocode_result[3].strip('()').split(',')
        if address_components[0] != '':
            new_component = {
                'types': ['street_number'],
                'short_name': address_components[0],
                'long_name': address_components[0],
            }
            json_result['address_components'].append(new_component)

        if address_components[2] != '':
            address_street = []
            if address_components[1] != '':
                address_street.append(address_components[1])
            address_street.append(address_components[2])
            if address_components[3]:
                address_street.append(address_components[3])
            if address_components[4]:
                address_street.append(address_components[4])
            new_component = {
                'types': ['route'],
                'short_name': " ".join(item for item in address_street),
                'long_name': " ".join(item for item in address_street),
            }
            json_result['address_components'].append(new_component)

        if address_components[5] != '':
            new_component = {
                'types': ['subpremise'],
                'short_name': address_components[5].strip('"'),
                'long_name': address_components[5].strip('"'),
            }
            json_result['address_components'].append(new_component)

        if address_components[6] != '':
            new_component = {
                'types': ['locality', 'political'],
                'short_name': address_components[6],
                'long_name': address_components[6],
            }
            json_result['address_components'].append(new_component)

        if address_components[7] != '':
            new_component = {
                'types': ['administrative_area_level_1', 'political'],
                'short_name': address_components[7],
                'long_name': address_components[7],
            }
            json_result['address_components'].append(new_component)

        if address_components[8] != '':
            new_component = {
                'types': ['postal_code'],
                'short_name': address_components[8],
                'long_name': address_components[8],
            }
            json_result['address_components'].append(new_component)

        new_component = {
            'types': ['country', 'political'],
            'short_name': 'US',
            'long_name': 'United States',
        }
        json_result['address_components'].append(new_component)

        # Finally, add the result we've just constructed to the list of
        # all results for this address.
        results.append(json_result)

    json_response = {}
    json_response['results'] = results
    json_response['status'] = "OK"

    return HttpResponse(simplejson.dumps(json_response, indent=4), mimetype="application/json")
