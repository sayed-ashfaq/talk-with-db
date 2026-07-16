class NL2SQLError(Exception):
    pass


class DatabaseConnectionError(NL2SQLError):
    pass


class UnsafeSQLError(NL2SQLError):
    pass


class SQLExecutionError(NL2SQLError):
    pass
