from django.conf.urls import patterns


urlpatterns = patterns('',
    (r'^api/geocode/json$', 'postgis_geocoder.views.google_style'),
)
