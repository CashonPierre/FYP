from enum import auto
from .upper_str_enum import UpperStrEnum


class PayloadEnum(UpperStrEnum):
    """The JWT might used for different purpose?"""

    VERIFICATION = auto()
    LOGIN = auto()
