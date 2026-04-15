# STL
from enum import auto

# Custom
from .upper_str_enum import UpperStrEnum


class ExceptionEnum(UpperStrEnum):
    APP_ERROR = auto()
    NOT_FOUND = auto()
    CONFLICT = auto()
    ALREADY_EXIST = auto()
    INVALID_CREDENTIALS = auto()
    INVALID_TOKEN = auto()
    TOKEN_EXPIRED = auto()
