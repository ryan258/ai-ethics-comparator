"""
Typed exceptions for query execution and provider boundaries.
"""

from __future__ import annotations


class QueryExecutionError(Exception):
    """Base exception for query execution failures."""


class RetryableQueryError(QueryExecutionError):
    """Base exception for failures that should be retried automatically."""


class RateLimitError(RetryableQueryError):
    """The provider rate-limited the request."""


class QueryTimeoutError(RetryableQueryError):
    """A provider or network timeout interrupted the request."""


class ProviderTransientError(RetryableQueryError):
    """A transient provider or transport error occurred."""


class InvalidModelOutputError(RetryableQueryError):
    """The provider returned unusable output."""


class ParseAmbiguityError(RetryableQueryError):
    """The model returned an ambiguous decision that could not be accepted."""


class MissingExplanationError(RetryableQueryError):
    """The model selected an option without the required explanation."""


class InvalidChoiceError(RetryableQueryError):
    """The model did not return a valid single choice."""


class AuthenticationError(QueryExecutionError):
    """The provider rejected the API credentials."""


class QuotaError(QueryExecutionError):
    """The provider rejected the request due to billing or quota."""


class ModelNotFoundError(QueryExecutionError):
    """The requested model is not available."""


class ProviderRefusedError(QueryExecutionError):
    """The provider rejected the request in a way that will not succeed on retry."""


class RunCancelledError(QueryExecutionError):
    """The run was cancelled by the user."""


def safe_error_message(exc: BaseException) -> str:
    """Map an exception to a message that is safe to persist or show a client.

    Provider exceptions embed raw upstream response bodies. Those belong in the
    server log, not in a stored run record or an HTTP response, so callers get
    the category and the log keeps the detail.
    """
    if isinstance(exc, AuthenticationError):
        return "The provider rejected the API key."
    if isinstance(exc, QuotaError):
        return "Insufficient API credits for this model."
    if isinstance(exc, ModelNotFoundError):
        return "The selected model is not available."
    if isinstance(exc, RateLimitError):
        return "The provider rate-limited this run."
    if isinstance(exc, QueryTimeoutError):
        return "The provider timed out."
    if isinstance(exc, InvalidModelOutputError):
        return "The model returned unusable output."
    if isinstance(exc, RunCancelledError):
        return "Run cancelled by user."
    if isinstance(exc, ProviderRefusedError):
        return "The provider refused this request."
    if isinstance(exc, QueryExecutionError):
        return "The model provider returned an error."
    if isinstance(exc, ValueError):
        return str(exc)
    return "The run could not be completed."
