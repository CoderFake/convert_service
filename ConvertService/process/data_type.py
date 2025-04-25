import enum


class HeaderType(enum.Enum):
    INPUT = 'input'
    DISPLAY = 'display'
    SYSTEM_OUTPUT = 'system_output'
    AGENCY_OUTPUT = 'agency_output'


class DisplayType(enum.Enum):
    SHOW = True
    HIDDEN = False
    ALL = None


class DownloadType(enum.Enum):
    SYSTEM = 'kenkoshisutemu'
    AGENCY = 'yoyaku_daikou'


