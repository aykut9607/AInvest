from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """Same response wrapper as the .NET services ({ data, success, message }), so the AI service's tools
    can read every backend the same way: success=false means data is null and the tool must say "I don't know"."""

    data: T | None = None
    success: bool
    message: str

    @classmethod
    def ok(cls, data: T, message: str) -> "Envelope[T]":
        return cls(data=data, success=True, message=message)

    @classmethod
    def error(cls, message: str) -> "Envelope[T]":
        return cls(data=None, success=False, message=message)
