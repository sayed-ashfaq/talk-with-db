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
