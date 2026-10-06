"""Display-only numbers; canonical amounts and stored evidence stay unchanged."""

from decimal import Decimal, localcontext


def readable_number(value: Decimal, *, places: int = 8) -> str:
    with localcontext() as context:
        context.prec = max(50, len(value.as_tuple().digits) + places + 2)
        rounded = value.quantize(Decimal(1).scaleb(-places))
    text = format(rounded, ",f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return ("≈" if rounded != value else "") + text


def readable_price(value: Decimal, tick_size: Decimal) -> str:
    exponent = tick_size.normalize().as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("Display tick size must be finite.")
    return readable_number(value, places=min(8, max(0, -exponent)))


def readable_percentage(fraction: Decimal) -> str:
    return readable_number(fraction * 100, places=4) + "%"
