from enum import auto

from .upper_str_enum import UpperStrEnum


class RequestEnum(UpperStrEnum):
    GET = auto()
    POST = auto()
    DELETE = auto()
    PATCH = auto()
    PUT = auto()
    HEADER = auto()
    OPTIONS = auto()
