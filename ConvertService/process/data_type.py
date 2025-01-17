import enum


class HeaderType(enum.Enum):
    BEFORE = 'input'
    FORMAT = 'format'
    AFTER = 'output'


class DisplayType(enum.Enum):
    SHOW = True
    HIDDEN = False
    ALL = None

