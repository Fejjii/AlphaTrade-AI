"""Pin Decimal arithmetic without changing the caller's process-wide context."""

from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Context, localcontext
from functools import wraps


def research_arithmetic[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
            return function(*args, **kwargs)

    return wrapped
