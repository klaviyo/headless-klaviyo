import json
import os

import rich_click as click
import survey

from kcli.constants import CAMPAIGN_CHANNELS, CAMPAIGN_GENERATE_CHANNELS, OverwriteMode, ResourceType, BLOCK_TYPES, \
    BLOCK_DISPLAY_OPTIONS
from kcli.helpers import KCLIState, style_prompt_string, campaign_send_strategy_prompt, campaign_tracking_prompt, \
    format_filename

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
    def callback(context, parameter, value):
        if context.obj.message_channel != 'email':
            return None
        if not value:
            value = survey.routines.input('Enter the label for the email message (optional): ')
        return value

    return click.option('--email-label', help='Label (email campaigns only)',
                        callback=callback)(f)


def campaign_email_subject_option(f):
    def callback(context, parameter, value):
        if context.obj.message_channel != 'email':
            return None
        if not value:
            value = survey.routines.input('Enter the subject line for the email message: ')
        return value

    return click.option('--email-subject', help='Subject line (email campaigns only)',
                        callback=callback)(f)


def campaign_email_preview_text_option(f):
    def callback(context, parameter, value):
        if context.obj.message_channel != 'email':
            return None
        if not value:
            value = survey.routines.input('Enter preview text for the email message (optional): ')
        return value

    return click.option('--email-preview-text', help='Preview text (email campaigns only)',
                        callback=callback)(f)


def campaign_sms_body_option(f):
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
    def callback(context, parameter, value):
        if not value:
            value = BLOCK_TYPES[
                survey.routines.select('Select the block type for the content block: ', options=BLOCK_TYPES)]
        return value

    return click.option('--block-type', help='Block type for the content block', type=click.Choice(BLOCK_TYPES),
                        callback=callback)(f)


def block_display_option(f):
    def callback(context, parameter, value):
        if not value:
            value = BLOCK_DISPLAY_OPTIONS[survey.routines.select('On which devices should the block be displayed?  ',
                                                                 options=BLOCK_DISPLAY_OPTIONS)]
        return value

    return click.option('--display', help='Where the block should display', type=click.Choice(BLOCK_DISPLAY_OPTIONS),
                        callback=callback)(f)


@click.group
@click.pass_context
def cli(context):
    pass


@cli.group
@click.pass_context
def get(context):
    """Retrieve Klaviyo resources and store them to files"""
    pass


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
    context.obj.info_message('Retrieving flow definitions...', bold=True)
    flows_data = context.obj.get_all_pages(context.obj.klaviyo.Flows.get_flows)
    context.obj.write_resource_data_list(flows_data, ResourceType.FLOW, flow_path, overwrite_mode)


@get.command(name='flow')
@common_options
@write_options(ResourceType.FLOW)
@click.argument('flow_id')
@click.pass_context
def get_flow(context, flow_id: str, flow_path: str, overwrite_mode: OverwriteMode):
    """Retrieve flow definition for a given flow ID"""
    context.obj.info_message(f'Retrieving flow with id {flow_id} ...', bold=True)
    flow = context.obj.klaviyo.Flows.get_flow(flow_id)
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
    click.echo(f'Generated block definition written to {format_filename(block_file)}. Edit that file to add {"styles and " if block_type == "text" else ""}content.')


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


if __name__ == '__main__':
    cli(max_content_width=120)
