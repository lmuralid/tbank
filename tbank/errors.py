"""Exceptions raised by the tbank package."""


class TBankError(Exception):
    """Base class for every tbank error."""


class NotFound(TBankError):
    """A member, claim, commitment or other record does not exist."""


class PermissionDenied(TBankError):
    """The acting member is not allowed to perform this operation."""


class InvalidOperation(TBankError):
    """The operation is not valid in the current state."""


class ValidationError(TBankError):
    """Input data or configuration is malformed."""


class AuthError(TBankError):
    """OTP or session verification failed."""
