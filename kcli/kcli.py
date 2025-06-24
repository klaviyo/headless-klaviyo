import json
import os

import rich_click as click
import survey

from kcli.constants import CAMPAIGN_CHANNELS, CAMPAIGN_GENERATE_CHANNELS, OverwriteMode, ResourceType, BLOCK_TYPES, \
    BLOCK_DISPLAY_OPTIONS, REPORT_TIMEFRAME_OPTIONS, REPORT_INTERVAL_OPTIONS, ReportResource, \
    REPORT_STATISTICS, ReportType, REPORT_GROUP_BY_OPTIONS
from kcli.helpers import KCLIState, style_prompt_string, campaign_send_strategy_prompt, campaign_tracking_prompt, \
    format_filename, statistics_prompt

click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.MAX_WIDTH = 120


def verbose_option(f):
    """Option to specify whether to use verbose output mode"""

    def callback(context, parameter, value):
        if value:
            if not context.obj:
                context.obj = KCLIState(verbose=True)
            else:
                context.obj.verbose = True

    return click.option('--verbose', '-v', is_flag=True, expose_value=False, help='Enable verbose output',
                        callback=callback)(f)


def api_key_option(f):
    """Option to specify the Klaviyo private API key to use for API calls"""

    def callback(context, parameter, value):
        if context.obj:
            context.obj.api_key = value
            context.obj.initialize_client()
        else:
            context.obj = KCLIState(api_key=value)

    return click.option('--api-key', envvar='KLAVIYO_API_KEY', required=True, expose_value=False,
                        help='Klaviyo account private API key', callback=callback,
                        show_envvar=True)(f)


def common_options(f):
    """Decorator to apply options that should be available to most commands"""
    return verbose_option(api_key_option(f))


def path_options(command_resource_type: ResourceType):
    """Options for specifying a path to use for resource definitions"""

    def path_option(path_resource_type: ResourceType):
        return click.option(f'--{path_resource_type.value}-path',
                            default=os.path.join(os.getcwd(), f'{path_resource_type.value}s'),
                            type=click.Path(file_okay=False), envvar=f'KLAVIYO_{path_resource_type.value.upper()}_PATH',
                            help=f'Directory to use for {path_resource_type.value} definitions',
                            show_default=True, show_envvar=True)

    def decorator(f):
        if command_resource_type == ResourceType.ALL:
            for resource_type in ResourceType:
                if resource_type != ResourceType.ALL:
                    f = path_option(resource_type)(f)
        else:
            f = path_option(command_resource_type)(f)
        return f

    return decorator


def overwrite_mode_option(resource_type: ResourceType):
    """Option for specifying whether to overwrite existing definition files"""
    resource_definitions = f'{resource_type.value} definitions' if resource_type != ResourceType.ALL else 'definitions'

    def decorator(f):
        return click.option('--overwrite-mode', default=OverwriteMode.INTERACTIVE.value,
                            type=click.Choice([mode.value for mode in OverwriteMode], case_sensitive=False),
                            envvar='KLAVIYO_OVERWRITE_MODE', show_envvar=True,
                            help=f'Determines if existing {resource_definitions} should be overwritten',
                            show_default=True)(f)

    return decorator


def stdout_option(f):
    """Option to specify whether to write result to stdout and suppress other output"""

    def callback(context, parameter, value):
        if value:
            if not context.obj:
                context.obj = KCLIState(stdout=True)
            else:
                context.obj.stdout = True

    return click.option('--stdout', is_flag=True, expose_value=False, envvar='KLAVIYO_STDOUT', show_envvar=True,
                        help='Output result to stdout instead of file and suppress other output', callback=callback)(f)


def write_options(resource_type: ResourceType):
    """Decorator to apply options used by commands that write definition files"""

    def decorator(f):
        f = path_options(resource_type)(f)
        f = overwrite_mode_option(resource_type)(f)
        f = stdout_option(f)
        return f

    return decorator


def read_options(resource_type: ResourceType, include_id_option: bool = True):
    """Decorator to apply options used by commands that read definition files"""

    def decorator(f):
        f = click.option(f'--{resource_type.value}-file', type=click.Path(dir_okay=False, allow_dash=True),
                         default=None,
                         help=f'Path to the {resource_type.value} definition file.')(f)
        if include_id_option:
            f = click.option(f'--{resource_type.value}-id',
                             help=f'ID of the {resource_type.value} to read from. The {resource_type.value} is read from stdin if neither this or --{resource_type.value}-file are provided.',
                             default=None)(f)
        return f

    return decorator


def campaign_audience_option(f):
    """Option to specify which lists/segments to include and exclude from a campaign audience"""

    def callback(context, parameter, value):
        if not value:
            return context.obj.campaign_audience_prompt()
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value
        if isinstance(parsed_value, dict):
            return {'included': parsed_value['included'], 'excluded': parsed_value['excluded']}
        elif isinstance(parsed_value, list):
            return {'included': parsed_value, 'excluded': []}
        else:
            return {'included': [parsed_value], 'excluded': []}

    return click.option('--audience',
                        help='List/segment id to include, array of list/segments ids to include, or object with "include" and "exclude" lists',
                        callback=callback)(f)


def campaign_message_channel_option(f):
    """Option to specify whether a campaign definition is for email or SMS"""

    def callback(context, parameter, value):
        if not value:
            value = CAMPAIGN_GENERATE_CHANNELS[survey.routines.select('Select the message channel for the campaign: ',
                                                                      options=CAMPAIGN_GENERATE_CHANNELS)]
        context.obj.message_channel = value
        return value

    return click.option('--message-channel', type=click.Choice(CAMPAIGN_GENERATE_CHANNELS),
                        help='Campaign message channel', callback=callback)(f)


def campaign_send_strategy_option(f):
    """Option for specifying the campaign sending strategy and schedule"""

    def callback(context, parameter, value):
        if not value:
            return campaign_send_strategy_prompt()
        return json.loads(value)

    return click.option('--send-strategy',
                        help='Object representing the campaign send strategy',
                        callback=callback)(f)


def campaign_tracking_option(f):
    """Option for specifying campaign tracking parameters and whether email clicks/opens should be tracked"""

    def callback(context, parameter, value):
        if not value:
            return campaign_tracking_prompt(context.obj.message_channel)
        return json.loads(value)

    return click.option('--tracking', help='Object representing the campaign tracking options', callback=callback)(f)


def campaign_email_label_option(f):
    """Option for specifying campaign email labels"""

    def callback(context, parameter, value):
        if context.obj.message_channel != 'email':
            return None
        if not value:
            value = survey.routines.input('Enter the label for the email message (optional): ')
        return value

    return click.option('--email-label', help='Label (email campaigns only)',
                        callback=callback)(f)


def campaign_email_subject_option(f):
    """Option for specifying email campaign subject"""

    def callback(context, parameter, value):
        if context.obj.message_channel != 'email':
            return None
        if not value:
            value = survey.routines.input('Enter the subject line for the email message: ')
        return value

    return click.option('--email-subject', help='Subject line (email campaigns only)',
                        callback=callback)(f)


def campaign_email_preview_text_option(f):
    """Option for specifying email campaign preview text"""

    def callback(context, parameter, value):
        if context.obj.message_channel != 'email':
            return None
        if not value:
            value = survey.routines.input('Enter preview text for the email message (optional): ')
        return value

    return click.option('--email-preview-text', help='Preview text (email campaigns only)',
                        callback=callback)(f)


def campaign_sms_body_option(f):
    """Option for specifying body text for SMS campaigns"""

    def callback(context, parameter, value):
        if context.obj.message_channel != 'sms':
            return None
        if not value:
            value = survey.routines.input('Enter the body text for the SMS message: ')
        return value

    return click.option('--sms-body',
                        help='Body text for the campaign (SMS campaigns only)',
                        callback=callback)(f)


def block_type_option(f):
    """Option for specifying text or HTML for universal content blocks"""

    def callback(context, parameter, value):
        if not value:
            value = BLOCK_TYPES[
                survey.routines.select('Select the block type for the content block: ', options=BLOCK_TYPES)]
        return value

    return click.option('--block-type', help='Block type for the content block', type=click.Choice(BLOCK_TYPES),
                        callback=callback)(f)


def block_display_option(f):
    """Option for specifying which devices should display a universal content block"""

    def callback(context, parameter, value):
        if not value:
            value = BLOCK_DISPLAY_OPTIONS[survey.routines.select('On which devices should the block be displayed?  ',
                                                                 options=BLOCK_DISPLAY_OPTIONS)]
        return value

    return click.option('--display', help='Where the block should display', type=click.Choice(BLOCK_DISPLAY_OPTIONS),
                        callback=callback)(f)


def report_statistics_option(report_resource: ReportResource):
    """Option for specifying which statistics to include in a campaign"""

    def decorator(f):
        def callback(context, parameter, value):
            if not value:
                return statistics_prompt(REPORT_STATISTICS[report_resource])
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                if value == 'all':
                    return REPORT_STATISTICS[report_resource]
                return value

        return click.option('--report-statistics',
                            help=f'{report_resource.value.capitalize()} statistics to report on. Accepts "all", an individual statistic, or array of statistics',
                            callback=callback)(f)

    return decorator


def conversion_metric_option(f):
    """Option for specifying which metric to use to calculate conversion related statistics"""

    def callback(context, parameter, value):
        if not value:
            return context.obj.conversion_metric_prompt()
        return value

    return click.option('--conversion-metric-id',
                        help='Metric ID to use to calculate conversion statistics',
                        callback=callback)(f)


def report_timeframe_option(f):
    """Option for specifying the timeframe for a report"""

    def callback(context, parameter, value):
        if not value:
            return REPORT_TIMEFRAME_OPTIONS[survey.routines.select('Select the timeframe for the report: ',
                                                                   options=REPORT_TIMEFRAME_OPTIONS)]
        return value

    return click.option('--timeframe', help='The timeframe for the report',
                        type=click.Choice(REPORT_TIMEFRAME_OPTIONS), callback=callback)(f)


def report_path_option(f):
    """Option for specifying the path to store generated reports"""
    return click.option('--report-path',
                        default=os.path.join(os.getcwd(), 'reports'),
                        type=click.Path(file_okay=False), envvar='KLAVIYO_REPORTS_PATH',
                        help='Directory to use to store reports',
                        show_default=True, show_envvar=True)(f)


def report_type_option(f):
    """Option for specifying whether a series or value report should be generated"""
    report_type_values = [report_type.value for report_type in ReportType]

    def callback(context, parameter, value):
        if not value:
            value = report_type_values[survey.routines.select('Should the report be a series or value report? ',
                                                        options=report_type_values)]
        context.obj.report_type = ReportType(value)
        return context.obj.report_type

    return click.option('--report-type', help='Type of report', type=click.Choice(report_type_values),
                        callback=callback)(f)


def report_interval_option(f):
    """Option for specifying the interval for a series report. Not applicable to values reports"""

    def callback(context, parameter, value):
        if context.obj.report_type != ReportType.SERIES:
            return None
        if not value:
            return REPORT_INTERVAL_OPTIONS[survey.routines.select('What interval should be used for the series report? ',
                                                                  options=REPORT_INTERVAL_OPTIONS)]
        return value

    return click.option('--interval', help='Interval (series reports only)', type=click.Choice(REPORT_INTERVAL_OPTIONS),
                        callback=callback)(f)


def report_group_by_option(f):
    """Option for specifying the how to group the results for a form report"""

    def callback(context, parameter, value):
        if not value:
            return REPORT_GROUP_BY_OPTIONS[survey.routines.select('How should the report results be grouped? ',
                                                                  options=REPORT_GROUP_BY_OPTIONS)]
        return value

    return click.option('--group-by', help='How to group report results', type=click.Choice(REPORT_GROUP_BY_OPTIONS),
                        callback=callback)(f)


def report_options(report_resource: ReportResource):
    """Options relevant to report command"""

    def decorator(f):
        if report_resource == ReportResource.FORM:
            f = report_group_by_option(f)
        if report_resource != ReportResource.CAMPAIGN:
            f = report_interval_option(f)
            f = report_type_option(f)
        if report_resource in [ReportResource.CAMPAIGN, ReportResource.FLOW]:
            f = conversion_metric_option(f)
        f = report_statistics_option(report_resource)(f)
        f = report_timeframe_option(f)
        f = report_path_option(f)
        return f

    return decorator


@click.group
@click.pass_context
def cli(context):
    pass


@cli.group
@click.pass_context
def get(context):
    """Retrieve Klaviyo resources and store them to files"""
    pass


@cli.group()
@click.pass_context
def set(context):
    """Set configuration options for the cli"""


@set.command(name="api-key")
@click.option(
    "--api-key", prompt=True, hide_input=True, help="Klaviyo API key to use for API calls"
)
@click.pass_context
def set_api_key(context, api_key: str):
    """Set the Klaviyo API key to use for API calls and save it to .env file"""
    env_path = os.path.join(os.getcwd(), ".env")
    existing_lines = []

    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as env_file:
            existing_lines = env_file.readlines()

        existing_lines = [
            line for line in existing_lines if not line.strip().startswith("KLAVIYO_API_KEY=")
        ]

    existing_lines.append(f"KLAVIYO_API_KEY={api_key}\n")

    with open(env_path, "w", encoding="utf-8") as env_file:
        env_file.writelines(existing_lines)

    if context.obj is None:
        context.obj = KCLIState(api_key=api_key)
    else:
        context.obj.api_key = api_key

    context.obj.initialize_client()
    context.obj.info_message(f"Klaviyo API key set and saved to .env file at {env_path}", bold=True)


@get.command(name='segments')
@common_options
@write_options(ResourceType.SEGMENT)
@click.pass_context
def get_segments(context, segment_path: str, overwrite_mode: OverwriteMode):
    """Retrieve segment definitions and store them to files"""
    context.obj.info_message('Retrieving segment definitions...', bold=True)
    segments_data = context.obj.get_all_pages(context.obj.klaviyo.Segments.get_segments)
    context.obj.write_resource_data_list(segments_data, ResourceType.SEGMENT, segment_path, overwrite_mode)


@get.command(name='segment')
@common_options
@write_options(ResourceType.SEGMENT)
@click.argument('segment_id')
@click.pass_context
def get_segment(context, segment_path: str, segment_id: str, overwrite_mode: OverwriteMode):
    """Retrieve a segment definition for a given segment ID"""
    context.obj.info_message(f'Retrieving segment definition for segment with id {segment_id} ...', bold=True)
    segment = context.obj.klaviyo.Segments.get_segment(segment_id)
    context.obj.write_resource_data_list(segment['data'], ResourceType.SEGMENT, segment_path, overwrite_mode)


@get.command(name='blocks')
@common_options
@write_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@click.pass_context
def get_universal_content_blocks(context, block_path: str, overwrite_mode: OverwriteMode):
    """Retrieve universal content block definitions and store them to files"""
    context.obj.info_message('Retrieving universal content blocks...', bold=True)
    blocks_data = context.obj.get_all_pages(context.obj.klaviyo.Templates.get_all_universal_content)
    context.obj.write_resource_data_list(blocks_data, ResourceType.UNIVERSAL_CONTENT_BLOCK, block_path, overwrite_mode)


@get.command(name='block')
@common_options
@write_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@click.argument('block_id')
@click.pass_context
def get_universal_content_block(context, block_id: str, block_path: str, overwrite_mode: OverwriteMode):
    """Retrieve universal content block definition for a given block ID"""
    context.obj.info_message(f'Retrieving universal content block with id {block_id} ...', bold=True)
    block = context.obj.klaviyo.Templates.get_universal_content(block_id)
    context.obj.write_resource_data_list(block['data'], ResourceType.UNIVERSAL_CONTENT_BLOCK, block_path,
                                         overwrite_mode)


@get.command(name='flows')
@common_options
@write_options(ResourceType.FLOW)
@click.pass_context
def get_flows(context, flow_path: str, overwrite_mode: OverwriteMode):
    """Retrieve flow definitions and store them to files"""
    def get_flows_with_definition(**kwargs):
        flows = context.obj.klaviyo.Flows.get_flows(**kwargs)
        for i, flow in enumerate(flows['data']):
            context.obj.verbose_echo(f'Retrieving definition data for flow {flow["id"]}')
            flows['data'][i] = context.obj.klaviyo.Flows.get_flow(flow['id'], additional_fields_flow=['definition'])['data']
        return flows

    context.obj.info_message('Retrieving flow definitions...', bold=True)
    flows_data = context.obj.get_all_pages(get_flows_with_definition)
    context.obj.write_resource_data_list(flows_data, ResourceType.FLOW, flow_path, overwrite_mode)


@get.command(name='flow')
@common_options
@write_options(ResourceType.FLOW)
@click.argument('flow_id')
@click.pass_context
def get_flow(context, flow_id: str, flow_path: str, overwrite_mode: OverwriteMode):
    """Retrieve flow definition for a given flow ID"""
    context.obj.info_message(f'Retrieving flow with id {flow_id} ...', bold=True)
    flow = context.obj.klaviyo.Flows.get_flow(flow_id, additional_fields_flow=['definition'])
    context.obj.write_resource_data_list(flow['data'], ResourceType.FLOW, flow_path, overwrite_mode)


@get.command(name='campaigns')
@common_options
@write_options(ResourceType.CAMPAIGN)
@click.pass_context
def get_campaigns(context, campaign_path: str, overwrite_mode: OverwriteMode):
    """Retrieve campaign definitions and store them to files"""

    def campaign_request(channel: str):
        def get_campaigns_for_channel(**kwargs):
            return context.obj.klaviyo.Campaigns.get_campaigns(filter=f'equals(messages.channel,"{channel}")',
                                                               **kwargs)

        return get_campaigns_for_channel

    context.obj.info_message('Retrieving campaign definitions...', bold=True)
    campaigns_data = []
    for c in CAMPAIGN_CHANNELS:
        campaigns_data += context.obj.get_all_pages(campaign_request(c))
    context.obj.write_resource_data_list(campaigns_data, ResourceType.CAMPAIGN, campaign_path, overwrite_mode)


@get.command(name='campaign')
@common_options
@write_options(ResourceType.CAMPAIGN)
@click.argument('campaign_id')
@click.pass_context
def get_campaign(context, campaign_id: str, campaign_path: str, overwrite_mode: OverwriteMode):
    """Retrieve campaign definition for a given campaign ID"""
    context.obj.info_message(f'Retrieving campaign with id {campaign_id} ...', bold=True)
    campaign = context.obj.klaviyo.Campaigns.get_campaign(campaign_id)
    context.obj.write_resource_data_list(campaign['data'], ResourceType.CAMPAIGN, campaign_path, overwrite_mode)


@get.command(name='all')
@common_options
@write_options(ResourceType.ALL)
@click.pass_context
def get_all(context, segment_path: str, block_path: str, flow_path: str, campaign_path: str,
            overwrite_mode: OverwriteMode):
    """Retrieve segments, universal content blocks, flows, and campaigns"""
    for command in [get_segments, get_universal_content_blocks, get_flows, get_campaigns]:
        context.invoke(command, overwrite_mode=overwrite_mode)


@cli.group
@click.pass_context
def create(context):
    """Create a new Klaviyo resource using a local definition file"""
    pass


@create.command(name='segment')
@common_options
@path_options(ResourceType.SEGMENT)
@read_options(ResourceType.SEGMENT, False)
@click.pass_context
def create_segment(context, segment_file: str, segment_path: str):
    """Push a new local segment definition to Klaviyo"""
    context.obj.create_resource(ResourceType.SEGMENT, segment_file, segment_path)


@create.command(name='flow')
@common_options
@path_options(ResourceType.FLOW)
@read_options(ResourceType.FLOW, False)
@click.pass_context
def create_flow(context, flow_file: str, flow_path: str):
    """Push a new local flow definition to Klaviyo"""
    context.obj.create_resource(ResourceType.FLOW, flow_file, flow_path)


@create.command(name='campaign')
@common_options
@path_options(ResourceType.CAMPAIGN)
@read_options(ResourceType.CAMPAIGN, False)
@click.pass_context
def create_campaign(context, campaign_file: str, campaign_path: str):
    """Push a new local campaign definition to Klaviyo"""
    context.obj.create_resource(ResourceType.CAMPAIGN, campaign_file, campaign_path)


@create.command(name='block')
@common_options
@path_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@read_options(ResourceType.UNIVERSAL_CONTENT_BLOCK, False)
@click.pass_context
def create_block(context, block_file: str, block_path: str):
    """Push a new local universal content block definition to Klaviyo"""
    context.obj.create_resource(ResourceType.UNIVERSAL_CONTENT_BLOCK, block_file, block_path)


@cli.group
@click.pass_context
def update(context):
    """Push an updated local resource definition to Klaviyo"""
    pass


@update.command(name='segment')
@common_options
@path_options(ResourceType.SEGMENT)
@read_options(ResourceType.SEGMENT)
@click.pass_context
def update_segment(context, segment_file: str, segment_id: str, segment_path: str):
    """Push an updated local segment definition to Klaviyo"""
    context.obj.update_resource(ResourceType.SEGMENT, segment_file, segment_id, segment_path)


@update.command(name='flow')
@common_options
@path_options(ResourceType.FLOW)
@read_options(ResourceType.FLOW)
@click.pass_context
def update_flow(context, flow_file: str, flow_id: str, flow_path: str):
    """Push an updated local flow definition to Klaviyo"""
    context.obj.update_resource(ResourceType.FLOW, flow_file, flow_id, flow_path)


@update.command(name='campaign')
@common_options
@path_options(ResourceType.CAMPAIGN)
@read_options(ResourceType.CAMPAIGN)
@click.pass_context
def update_campaign(context, campaign_file: str, campaign_id: str, campaign_path: str):
    """Push an updated local campaign definition to Klaviyo"""
    context.obj.update_resource(ResourceType.CAMPAIGN, campaign_file, campaign_id, campaign_path)


@update.command(name='block')
@common_options
@path_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@read_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@click.pass_context
def update_block(context, block_file, block_id, block_path):
    """Push an updated local universal content block definition to Klaviyo"""
    context.obj.update_resource(ResourceType.UNIVERSAL_CONTENT_BLOCK, block_file, block_id, block_path)


@cli.group
@click.pass_context
def generate(context):
    """Create a local resource definition file"""
    pass


@generate.command(name='campaign')
@common_options
@path_options(ResourceType.CAMPAIGN)
@click.option('--name', prompt=style_prompt_string('Campaign name'), help='Campaign name')
@campaign_audience_option
@campaign_send_strategy_option
@campaign_message_channel_option
@campaign_tracking_option
@campaign_email_label_option
@campaign_email_subject_option
@campaign_email_preview_text_option
@campaign_sms_body_option
@click.pass_context
def generate_campaign(context, campaign_path: str, name: str, audience: dict,
                      send_strategy: dict, message_channel: click.Choice, tracking: dict,
                      email_label: str, email_subject: str, email_preview_text: str,
                      sms_body: str):
    """Create a new local campaign definition file. Provides interactive prompts for parameters not provided via command line options."""
    if message_channel == 'email':
        message_definition = {
            'content': {'subject': email_subject},
            'channel': 'email',
        }
        if email_preview_text != '':
            message_definition['content']['preview_text'] = email_preview_text
        if email_label != '':
            message_definition['label'] = email_label
    else:
        message_definition = {
            'content': {'body': sms_body},
            'channel': 'sms',
        }

    campaign_data = {
        'type': 'campaign',
        'attributes': {
            'name': name,
            'audiences': audience,
            'send_options': {
                'use_smart_sending': True
            },
            'send_strategy': send_strategy,
            'tracking_options': tracking,
            'campaign-messages': {
                'data': [
                    {
                        'type': 'campaign-message',
                        'attributes': {
                            'definition': message_definition
                        }
                    }
                ]
            }
        },
    }
    campaign_file = context.obj.write_generated_data_to_file(ResourceType.CAMPAIGN, campaign_data, campaign_path)
    click.echo(f'Generated campaign definition written to {format_filename(campaign_file)}')


@generate.command(name='block')
@common_options
@path_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@click.option('--name', prompt=style_prompt_string('Content block name'), help='Content block name')
@block_type_option
@block_display_option
@click.pass_context
def generate_block(context, block_path: str, name: str, block_type: str, display: str):
    """Create a new local universal content block definition file. Provides interactive prompts for parameters not provided via command line options."""
    block_data = {
        'type': 'template-universal-content',
        'attributes': {
            'name': name,
            'definition': {
                'content_type': 'block',
                'type': block_type,
                'data': {
                    'content': "ADD CONTENT HERE",
                    'display_options': {
                        'show_on': display
                    }
                }
            }
        }
    }
    if block_type == 'text':
        block_data['attributes']['definition']['data']['styles'] = {}
    block_file = context.obj.write_generated_data_to_file(ResourceType.UNIVERSAL_CONTENT_BLOCK, block_data, block_path)
    click.echo(
        f'Generated block definition written to {format_filename(block_file)}. Edit that file to add {"styles and " if block_type == "text" else ""}content.')


@cli.group
@click.pass_context
def inspect(context):
    """Inspect a local resource definition file"""


@inspect.command(name='campaign')
@common_options
@path_options(ResourceType.CAMPAIGN)
@read_options(ResourceType.CAMPAIGN)
@click.pass_context
def inspect_campaign(context, campaign_path: str, campaign_file: str, campaign_id: str):
    """Inspect a local campaign definition file"""
    context.obj.inspect_resource(ResourceType.CAMPAIGN, campaign_path, campaign_file, campaign_id)


@inspect.command(name='block')
@common_options
@path_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@read_options(ResourceType.UNIVERSAL_CONTENT_BLOCK)
@click.pass_context
def inspect_block(context, block_path: str, block_file: str, block_id: str):
    """Inspect a local universal content block definition file"""
    context.obj.inspect_resource(ResourceType.UNIVERSAL_CONTENT_BLOCK, block_path, block_file, block_id)


@inspect.command(name='flow')
@common_options
@path_options(ResourceType.FLOW)
@read_options(ResourceType.FLOW)
@click.pass_context
def inspect_flow(context, flow_path: str, flow_file: str, flow_id: str):
    """Inspect a local flow definition file"""
    context.obj.inspect_resource(ResourceType.FLOW, flow_path, flow_file, flow_id)


@inspect.command(name='segment')
@common_options
@path_options(ResourceType.SEGMENT)
@read_options(ResourceType.SEGMENT)
@click.pass_context
def inspect_segment(context, segment_path: str, segment_file: str, segment_id: str):
    """Inspect a local segment definition file"""
    context.obj.inspect_resource(ResourceType.SEGMENT, segment_path, segment_file, segment_id)


@cli.group
@click.pass_context
def delete(context):
    """Delete a resource from Klaviyo"""


@delete.command(name='campaign')
@common_options
@click.argument('campaign_id')
@click.pass_context
def delete_campaign(context, campaign_id: str):
    """Delete a campaign from Klaviyo"""
    context.obj.delete_resource(ResourceType.CAMPAIGN, campaign_id)


@delete.command(name='block')
@common_options
@click.argument('block_id')
@click.pass_context
def delete_block(context, block_id: str):
    """Delete a universal content block from Klaviyo"""
    context.obj.delete_resource(ResourceType.UNIVERSAL_CONTENT_BLOCK, block_id)


@delete.command(name='flow')
@common_options
@click.argument('flow_id')
@click.pass_context
def delete_flow(context, flow_id: str):
    """Delete a flow from Klaviyo"""
    context.obj.delete_resource(ResourceType.FLOW, flow_id)


@delete.command(name='segment')
@common_options
@click.argument('segment_id')
@click.pass_context
def delete_segment(context, segment_id: str):
    """Delete a segment from Klaviyo"""
    context.obj.delete_resource(ResourceType.SEGMENT, segment_id)


@cli.group
@click.pass_context
def report(context):
    """Generate a report file"""
    pass


@report.command(name='campaign')
@common_options
@report_options(ReportResource.CAMPAIGN)
@click.argument('campaign_id')
@click.pass_context
def report_campaign(context, report_statistics: list[str], conversion_metric_id: str, report_path: str, timeframe: str,
                    campaign_id: str):
    """Generate a report file about campaign performance data. Provides interactive prompts for parameters not provided via command line options."""
    context.obj.report(ReportResource.CAMPAIGN, ReportType.VALUES, report_statistics, report_path, timeframe,
               campaign_id, None, conversion_metric_id, None)


@report.command(name='flow')
@common_options
@report_options(ReportResource.FLOW)
@click.argument('flow_id')
@click.pass_context
def report_flow(context, report_type: ReportType, report_statistics: list[str], conversion_metric_id: str,
                report_path: str, timeframe: str, flow_id: str, interval: str):
    """Generate a report file about flow performance data. Provides interactive prompts for parameters not provided via command line options."""
    context.obj.report(ReportResource.FLOW, report_type, report_statistics, report_path, timeframe, flow_id, interval,
                       conversion_metric_id, None)


@report.command(name='form')
@common_options
@report_options(ReportResource.FORM)
@click.argument('form_id')
@click.pass_context
def report_flow(context, report_type: ReportType, report_statistics: list[str],
                report_path: str, timeframe: str, form_id: str, interval: str, group_by: str):
    """Generate a report file about form performance data. Provides interactive prompts for parameters not provided via command line options."""
    context.obj.report(ReportResource.FORM, report_type, report_statistics, report_path, timeframe, form_id, interval,
                       None, group_by)


@report.command(name='segment')
@common_options
@report_options(ReportResource.SEGMENT)
@click.argument('segment_id')
@click.pass_context
def report_segment(context, report_type: ReportType, report_statistics: list[str], report_path: str, timeframe: str,
                   segment_id: str, interval: str):
    """Generate a report file about segment membership data. Provides interactive prompts for parameters not provided via command line options."""
    context.obj.report(ReportResource.SEGMENT, report_type, report_statistics, report_path, timeframe, segment_id,
                       interval, None, None)


if __name__ == '__main__':
    cli(max_content_width=120)
