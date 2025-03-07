from enum import Enum


CAMPAIGN_CHANNELS = ['email', 'sms', 'mobile_push']
CAMPAIGN_GENERATE_CHANNELS = ['email', 'sms']
BLOCK_TYPES = ['text', 'html']
BLOCK_DISPLAY_OPTIONS = ['all', 'desktop', 'mobile']

TABLE_INDENT = 6
TABLE_HEADER_HEIGHT = 4
TABLE_FOOTER_HEIGHT = 2
DATETIME_LENGTH = 19

class OverwriteMode(Enum):
    OVERWRITE = 'overwrite'
    INTERACTIVE = 'interactive'
    KEEP_LOCAL = 'keep-local'


class ResourceType(Enum):
    SEGMENT = 'segment'
    UNIVERSAL_CONTENT_BLOCK = 'block'
    FLOW = 'flow'
    CAMPAIGN = 'campaign'
    ALL = 'all'