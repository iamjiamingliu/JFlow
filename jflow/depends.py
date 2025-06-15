from typing import (
    Awaitable,
    Callable,
    TypeVar,
    ParamSpec,
    cast,
)

P = ParamSpec("P")
T = TypeVar("T")

class _DependsSentinel:
    def __init__(self, dependency: Callable[P, Awaitable[T]]) -> None:
        self.dependency: Callable[P, Awaitable[T]] = dependency

def Depends(dependency: Callable[P, Awaitable[T]]) -> T:
    return cast(T, _DependsSentinel(dependency))
