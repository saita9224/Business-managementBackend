from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


def to_decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{field_name} must be a valid number.")