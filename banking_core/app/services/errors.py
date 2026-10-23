class BankingError(Exception):
    code = "BANKING_ERROR"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(BankingError):
    code = "NOT_FOUND"
    status_code = 404


class ForbiddenError(BankingError):
    code = "FORBIDDEN"
    status_code = 403


class ValidationError(BankingError):
    code = "VALIDATION_ERROR"
    status_code = 422


class ConflictError(BankingError):
    code = "CONFLICT"
    status_code = 409


class InsufficientFundsError(BankingError):
    code = "INSUFFICIENT_FUNDS"
    status_code = 409


class AuthorizationError(BankingError):
    code = "AUTHORIZATION_REQUIRED"
    status_code = 403
