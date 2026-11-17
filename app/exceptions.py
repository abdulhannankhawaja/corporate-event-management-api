"""Application exception types."""


class AppError(Exception):
    """Represent an expected API error."""

    def __init__(self, status_code: int, detail: str) -> None:
        """Initialize an application error."""
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    """Represent a resource-not-found error."""

    def __init__(self, detail: str) -> None:
        """Initialize a 404 application error."""
        super().__init__(status_code=404, detail=detail)


class ConflictError(AppError):
    """Represent a resource-conflict error."""

    def __init__(self, detail: str) -> None:
        """Initialize a 409 application error."""
        super().__init__(status_code=409, detail=detail)


class UnauthorizedError(AppError):
    """Represent an authentication error."""

    def __init__(self, detail: str) -> None:
        """Initialize a 401 application error."""
        super().__init__(status_code=401, detail=detail)
