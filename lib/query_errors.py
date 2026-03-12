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
