from distutils.core import setup

setup(
    name='Lieux',
    version='0.5.4',
    author='Allan James Vestal',
    author_email='ajvestal@journalsentinel.com',
    packages=['lieux'],
    description='A Djangonic wrapper around the PostGIS geocoder that emulates the Google Maps geocoder\'s API.',
    long_description=open('README.textile').read(),
    install_requires=[
        "Django >= 1.4",
    ],
)
