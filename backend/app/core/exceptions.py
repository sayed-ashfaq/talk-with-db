class NL2SQLError(Exception):
    pass


class DatabaseConnectionError(NL2SQLError):
    pass


class UnsafeSQLError(NL2SQLError):
    pass


class DestructiveSQLError(UnsafeSQLError):
    pass


class SQLExecutionError(NL2SQLError):
    pass


class AuthError(Exception):
    """Deliberately not an NL2SQLError: those all mean "something broke" and map to 500, whereas
    these are expected outcomes the client is supposed to act on. Each carries the status code its
    handler in main.py should return, so the service layer stays free of FastAPI imports."""

    status_code = 401
    detail = "authentication failed"

    def __init__(self, detail: str | None = None):
        self.detail = detail or type(self).detail
        super().__init__(self.detail)


class InvalidCredentialsError(AuthError):
    status_code = 401
    # identical whether the email is unknown or the password is wrong — anything more specific
    # turns the login form into a tool for discovering who has an account
    detail = "invalid email or password"


class NotAuthenticatedError(AuthError):
    status_code = 401
    detail = "not authenticated"


class EmailAlreadyRegisteredError(AuthError):
    status_code = 409
    detail = "an account with this email already exists"


class AccountDisabledError(AuthError):
    status_code = 403
    detail = "this account has been disabled"


class OAuthNotConfiguredError(AuthError):
    status_code = 503
    detail = "Google sign-in is not configured on this server"


class OAuthFailedError(AuthError):
    status_code = 400
    detail = "Google sign-in failed"
