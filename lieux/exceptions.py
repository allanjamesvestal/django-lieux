class BaseGeocoderException(Exception):
    """
    The base class for all errors raised by lieux.
    """
    def __init__(self, value):
        self.parameter = value

    def __str__(self):
        return repr(self.parameter)


class AddressInputError(BaseGeocoderException):
    """
    Raised when a user has entered a non-parsable address.
    """
    pass


class AddressNotFoundError(BaseGeocoderException):
    """
    Raised when no matches could be found for an address.
    """
    pass


class IntersectionInputError(BaseGeocoderException):
    """
    Raised when a user has entered a non-parsable intersection.
    """
    pass


class IntersectionNotFoundError(BaseGeocoderException):
    """
    Raised when no matches could be found for an intersection.
    """
    pass


class NoResultsError(BaseGeocoderException):
    """
    Raised when the search() function fails to generate any results.
    """
    pass
