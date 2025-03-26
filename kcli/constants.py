from enum import Enum


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

class ReportResource(Enum):
    SEGMENT = 'segment'
    FLOW = 'flow'
    CAMPAIGN = 'campaign'
    FORM = 'form'

class ReportType(Enum):
    SERIES = 'series'
    VALUES = 'values'

CAMPAIGN_CHANNELS = ['email', 'sms', 'mobile_push']
CAMPAIGN_GENERATE_CHANNELS = ['email', 'sms']
BLOCK_TYPES = ['text', 'html']
BLOCK_DISPLAY_OPTIONS = ['all', 'desktop', 'mobile']

REPORT_STATISTICS = {
    ReportResource.CAMPAIGN: [
        'average_order_value', 'bounce_rate', 'bounced', 'bounced_or_failed', 'bounced_or_failed_rate', 'click_rate',
        'click_to_open_rate', 'clicks', 'clicks_unique', 'conversion_rate', 'conversion_uniques', 'conversion_value',
        'conversions', 'delivered', 'delivery_rate', 'failed', 'failed_rate', 'open_rate', 'opens', 'opens_unique',
        'recipients', 'revenue_per_recipient', 'spam_complaint_rate', 'spam_complaints', 'unsubscribe_rate',
        'unsubscribe_uniques', 'unsubscribes'
    ],
    ReportResource.FLOW: [
        'average_order_value', 'bounce_rate', 'bounced', 'bounced_or_failed', 'bounced_or_failed_rate', 'click_rate',
        'click_to_open_rate', 'clicks', 'clicks_unique', 'conversion_rate', 'conversion_uniques', 'conversion_value',
        'conversions', 'delivered', 'delivery_rate', 'failed', 'failed_rate', 'open_rate', 'opens', 'opens_unique',
        'recipients', 'revenue_per_recipient', 'spam_complaint_rate', 'spam_complaints', 'unsubscribe_rate',
        'unsubscribe_uniques', 'unsubscribes'
    ],
    ReportResource.FORM: [
        'closed_form', 'closed_form_uniques', 'qualified_form', 'qualified_form_uniques', 'submit_rate', 'submits',
        'submitted_form_step', 'submitted_form_step_uniques', 'viewed_form', 'viewed_form_step',
        'viewed_form_step_uniques', 'viewed_form_uniques'
    ],
    ReportResource.SEGMENT: [
        'members_added', 'members_removed', 'net_members_changed', 'total_members'
    ]
}

REPORT_TIMEFRAME_OPTIONS = ['last_year', 'this_year', 'last_12_months', 'last_3_months', 'last_month', 'this_month',
                            'last_365_days', 'last_90_days', 'last_30_days', 'last_7_days', 'yesterday', 'today']
REPORT_INTERVAL_OPTIONS = ['hourly', 'daily', 'weekly', 'monthly']
REPORT_GROUP_BY_OPTIONS = ['form_id', 'form_version_id']

BASKET_TABLE_INDENT = 6
CHOOSE_TABLE_INDENT = 2
TABLE_HEADER_HEIGHT = 4
TABLE_FOOTER_HEIGHT = 2
DATETIME_LENGTH = 19
