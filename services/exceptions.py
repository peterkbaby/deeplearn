class ServiceError(Exception):
    """Base exception for service-layer (business logic) errors."""
    status_code: int = 400


class EmailAlreadyRegistered(ServiceError):
    status_code = 400


class UserNotFound(ServiceError):
    status_code = 404


class InvalidCredentials(ServiceError):
    status_code = 401


class OAuthProviderLogin(ServiceError):
    status_code = 401


class RefreshTokenMissing(ServiceError):
    status_code = 401


class InvalidRefreshToken(ServiceError):
    status_code = 401


class RefreshTokenRevoked(ServiceError):
    status_code = 401


class RefreshTokenExpired(ServiceError):
    status_code = 401


class OnboardingAlreadyCompleted(ServiceError):
    status_code = 400


class UsernameAlreadyExists(ServiceError):
    status_code = 400


class FileTooLarge(ServiceError):
    status_code = 400


class InvalidFileType(ServiceError):
    status_code = 400


class GoogleUserInfoMissing(ServiceError):
    status_code = 400
