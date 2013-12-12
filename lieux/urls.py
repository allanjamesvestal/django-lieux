from django.conf.urls import patterns


urlpatterns = patterns('',
    (r'^api/geocode/json$', 'lieux.views.google_style'),
)