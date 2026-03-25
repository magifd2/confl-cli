class CCLIError(Exception):
    def __init__(self, message: str, exit_code: int = 99) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class AuthError(CCLIError):
    def __init__(self, message: str = "Authentication failed. Check your credentials.") -> None:
        super().__init__(message, exit_code=1)


class ForbiddenError(CCLIError):
    def __init__(self, message: str = "Access denied.") -> None:
        super().__init__(message, exit_code=2)


class NotFoundError(CCLIError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message, exit_code=3)


class NetworkError(CCLIError):
    def __init__(self, message: str = "Network error occurred.") -> None:
        super().__init__(message, exit_code=4)


class RateLimitError(CCLIError):
    def __init__(self, message: str = "API rate limit exceeded.") -> None:
        super().__init__(message, exit_code=5)


class ConfigError(CCLIError):
    def __init__(self, message: str = "Configuration error.") -> None:
        super().__init__(message, exit_code=6)
