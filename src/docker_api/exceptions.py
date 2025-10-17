"""
Docker API Exceptions
"""


class DockerException(Exception):
    """Base Docker exception"""
    pass


class APIError(DockerException):
    """Docker API error"""
    
    def __init__(self, message, response=None, status_code=None):
        super().__init__(message)
        self.response = response
        self.status_code = status_code


class ImageNotFound(DockerException):
    """Image not found"""
    pass


class ContainerNotFound(DockerException):
    """Container not found"""
    pass


class NetworkNotFound(DockerException):
    """Network not found"""
    pass


class BuildError(DockerException):
    """Image build error"""
    pass
