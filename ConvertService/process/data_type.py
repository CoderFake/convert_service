import enum


class HeaderType(enum.Enum):
    BEFORE = 'input'
    FORMAT = 'format'
    AFTER = 'output'


class DisplayType(enum.Enum):
    SHOW = True
    HIDDEN = False
    ALL = None


class DownloadType(enum.Enum):
    SYSTEM = 'kenkoshisutemu'
    AGENCY = 'yoyaku_daikou'


