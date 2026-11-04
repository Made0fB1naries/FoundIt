"""Reusable functional-programming helpers used by FoundIt's domain services.

The collection helpers intentionally return tuples so callers receive immutable
results instead of mutable lists. The functions passed to these helpers are
first-class values, allowing the helpers to be reused across domain operations.
"""

from functools import reduce
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")


def map_values(function: Callable[[T], U], values: Iterable[T]) -> tuple[U, ...]:
    """Apply *function* to every value and return the results as a tuple."""
    return tuple(map(function, values))


def filter_values(predicate: Callable[[T], bool], values: Iterable[T]) -> tuple[T, ...]:
    """Keep values that satisfy *predicate* and return them as a tuple."""
    return tuple(filter(predicate, values))


def reduce_values(
    function: Callable[[U, T], U], values: Iterable[T], initial: U
) -> U:
    """Fold *values* into one result, starting with *initial*."""
    return reduce(function, values, initial)


def compose(*functions: Callable[[object], object]) -> Callable[[object], object]:
    """Compose functions right-to-left: compose(f, g)(x) == f(g(x))."""
    def composed(value):
        for function in reversed(functions):
            value = function(value)
        return value

    return composed


def pipe(value: T, *functions: Callable[[object], object]):
    """Apply functions left-to-right to an initial value."""
    for function in functions:
        value = function(value)
    return value


def all_of(*predicates: Callable[[T], bool]) -> Callable[[T], bool]:
    """Create a predicate that is true when every supplied predicate matches."""
    return lambda value: all(map(lambda predicate: predicate(value), predicates))


def any_of(*predicates: Callable[[T], bool]) -> Callable[[T], bool]:
    """Create a predicate that is true when at least one predicate matches."""
    return lambda value: any(map(lambda predicate: predicate(value), predicates))


def negate(predicate: Callable[[T], bool]) -> Callable[[T], bool]:
    """Return a new predicate with the opposite result."""
    return lambda value: not predicate(value)
