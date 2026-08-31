class MigratorError(Exception):
    """Expected, user-actionable failure."""


class ConfigError(MigratorError):
    pass


class PreflightError(MigratorError):
    pass
