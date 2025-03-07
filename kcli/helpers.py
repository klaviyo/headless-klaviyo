import copy
import datetime
import json
import os
import typing

import rich_click as click
import openapi_client
import survey
from rich.table import Table
from rich.console import Console
from klaviyo_api import KlaviyoAPI
from openapi_client.api_arg_options import USE_DICTIONARY_FOR_RESPONSE_DATA

from kcli.constants import OverwriteMode, ResourceType, TABLE_INDENT, TABLE_HEADER_HEIGHT, TABLE_FOOTER_HEIGHT, \
    DATETIME_LENGTH


class KCLIState(object):
    """Context object to maintain API client, global settings, and input/output"""

    def __init__(self, api_key: str | None = None, verbose: bool = False, stdout: bool = False):
        self.verbose = verbose
        self.api_key = api_key
        self.stdout = stdout
        self.klaviyo = None
        if self.api_key is not None:
            self.initialize_client()

    def initialize_client(self):
        self.klaviyo = KlaviyoAPI(self.api_key, max_delay=60, max_retries=3,
                                  options={USE_DICTIONARY_FOR_RESPONSE_DATA: True})
        self.klaviyo.api_client.default_headers['X-Klaviyo-API-Source'] = 'headless-klaviyo'

    def info_message(self, message: str, color: str | None = None, bold: bool = False):
        """Print an informational message. Skipped when using the --stdout flag"""
        if not self.stdout:
            click.secho(message, fg=color, bold=bold)

    def verbose_echo(self, message: str, color: str | None = None, bold: bool = False):
        """Print a message only when a command is using the --verbose flag"""
        if self.verbose:
            self.info_message(message, color, bold)

    def get_all_pages(self, request_function: typing.Callable):
        """Get data from all pages of a Klaviyo API request using cursor pagination"""
        data = []
        result = request_function()
        data += result['data']
        while result['links']['next']:
            self.verbose_echo(f'Retrieved {len(data)} results...')
            result = request_function(page_cursor=result['links']['next'])
            data += result['data']
        return data

    def write_resource_data_list(self, data: dict | list[dict], resource_type: ResourceType, path: str,
                                 overwrite_mode: OverwriteMode):
        """Write a dict or list of dicts representing resource definitions to a file or stdout depending on command settings"""
        individual_item = type(data) is not list
        if individual_item:
            data = [data]
        if len(data) == 0:
            click.echo(f'No {resource_type.value} definitions found.')
            return
        unchanged_count = 0
        keep_count = 0
        overwrite_count = 0
        new_count = 0
        os.makedirs(path, exist_ok=True)
        stdout_results = []
        for item in data:
            clean_resource_data(resource_type, item)
            if self.stdout:
                stdout_results.append(item)
            else:
                file_path = os.path.join(path, f'{resource_type.value}-{item["id"]}.json')
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        try:
                            existing_data = json.load(f)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            click.secho(
                                f'Existing file {format_filename(file_path)} does not contain expected data format.',
                                fg='red')
                            existing_data = None
                    if existing_data == item:
                        self.verbose_echo(f'{item["id"]} definition is unchanged.', color='green')
                        unchanged_count += 1
                        continue
                    if (
                            overwrite_mode == OverwriteMode.KEEP_LOCAL.value or
                            ((overwrite_mode == OverwriteMode.INTERACTIVE.value) and
                             not click.confirm(click.style(
                                 f'Overwrite existing {resource_type.value} definition with id {item["id"]}?',
                                 fg='yellow')))
                    ):
                        self.verbose_echo(
                            f'Keeping local definition for {resource_type.value} with id {item["id"]} in {file_path}',
                            color='green')
                        keep_count += 1
                        continue
                    else:
                        overwrite_count += 1
                else:
                    new_count += 1
                self.write_data_to_file(resource_type, item, file_path)
        if self.stdout:
            if individual_item:
                stdout_results = stdout_results[0]
            click.echo(json.dumps(stdout_results, indent=4))
        self.info_message(
            f'Retrieved {len(data)} {resource_type.value} {"definition" if len(data) == 1 else "definitions"}. '
            f'({unchanged_count} unchanged, {keep_count} skipped, {overwrite_count} overwritten, {new_count} new)')

    def write_data_to_file(self, resource_type: ResourceType, resource_data: dict, resource_file: str):
        """Write a dict representing a resource definition to a specified file"""
        os.makedirs(os.path.dirname(resource_file), exist_ok=True)
        with open(resource_file, 'w') as f:
            self.verbose_echo(f'Writing {resource_type.value} definition to {format_filename(resource_file)}')
            f.write(json.dumps(resource_data, indent=4))

    def write_generated_data_to_file(self, resource_type: ResourceType, resource_data: dict, resource_path: str):
        """Write a dict representing a resource definition to a new file. Returns file path for new file"""
        new_file_index = 0
        file_path = None
        while file_path is None or os.path.exists(file_path):
            new_file_index += 1
            file_path = os.path.join(resource_path, f'new_{resource_type.value}_{new_file_index}.json')
        self.write_data_to_file(resource_type, resource_data, file_path)
        return file_path

    def create_resource(self, resource_type: ResourceType, resource_file: str, resource_path: str):
        resource_file = resource_filename(resource_type, resource_path, resource_file, None)
        resource_data = read_resource_file(resource_file, resource_path)
        if resource_data is None:
            return
        if 'id' in resource_data:
            click.secho('Provided resource definition already has an id field. Use the update command to update an '
                        'existing resource, or clear the id field from the definition to create a new resource',
                        fg='red')
            return
        click.secho(
            f'Creating {resource_type.value} from {format_filename(resource_file)}...', bold=True)
        if resource_type == ResourceType.SEGMENT:
            segment_create_query = openapi_client.SegmentCreateQuery(data=resource_data)
            response = self.klaviyo.Segments.create_segment(segment_create_query)
        elif resource_type == ResourceType.UNIVERSAL_CONTENT_BLOCK:
            block_create_query = openapi_client.UniversalContentCreateQuery(data=resource_data)
            response = self.klaviyo.Templates.create_universal_content(block_create_query)
        elif resource_type == ResourceType.CAMPAIGN:
            campaign_create_query = openapi_client.CampaignCreateQuery(data=resource_data)
            response = self.klaviyo.Campaigns.create_campaign(campaign_create_query)
        elif resource_type == ResourceType.FLOW:
            flow_create_query = openapi_client.FlowCreateQuery(data=resource_data)
            response = self.klaviyo.Flows.create_flow(flow_create_query)
        else:
            raise ValueError('Unsupported resource type.')
        new_file_path = os.path.join(resource_path, f'{resource_type.value}-{response["data"]["id"]}.json')
        clean_resource_data(resource_type, response['data'])
        self.write_data_to_file(resource_type, response['data'], new_file_path)
        click.secho(
            f'The result from pushing {format_filename(resource_file)} to Klaviyo is written to {format_filename(new_file_path)}.',
            fg='yellow')

    def update_resource(self, resource_type: ResourceType, resource_file: str, resource_id: str, resource_path: str):
        resource_file = resource_filename(resource_type, resource_path, resource_file, resource_id)
        click.secho(
            f'Pushing {resource_type.value} definition from {format_filename(resource_file)} to Klaviyo...',
            bold=True)
        resource_data = read_resource_file(resource_file, resource_path)
        if resource_data is None:
            return
        if 'id' not in resource_data:
            click.secho('Provided resource definition does not have an id field. Use the create command to create a '
                        'new resource, or populate the id field in the definition to update an existing resource',
                        fg='red')
            return
        click.secho(
            f'Updating {resource_type.value} using {format_filename(resource_file)}...',
            bold=True)
        if resource_type == ResourceType.SEGMENT:
            segment_update_query = openapi_client.SegmentPartialUpdateQuery(data=resource_data)
            response = self.klaviyo.Segments.update_segment(segment_update_query.data.id, segment_update_query)
        elif resource_type == ResourceType.UNIVERSAL_CONTENT_BLOCK:
            block_update_query = openapi_client.UniversalContentPartialUpdateQuery(data=resource_data)
            response = self.klaviyo.Templates.update_universal_content(block_update_query.data.id,
                                                                       block_update_query)
        elif resource_type == ResourceType.CAMPAIGN:
            campaign_update_query = openapi_client.CampaignPartialUpdateQuery(data=resource_data)
            response = self.klaviyo.Campaigns.update_campaign(campaign_update_query.data.id,
                                                              campaign_update_query)
        elif resource_type == ResourceType.FLOW:
            # Only updates to flow status are supported through the API, not other flow parameters
            remote_flow = self.klaviyo.Flows.get_flow(resource_data['id'])['data']
            if resource_data == remote_flow:
                click.echo(f'There are no changes to flow {resource_data["id"]}. Skipping update.')
                return
            remote_flow_without_status = copy.deepcopy(remote_flow)
            del remote_flow_without_status['attributes']['status']
            flow_without_status = copy.deepcopy(resource_data)
            del flow_without_status['attributes']['status']
            if (resource_data['attributes']['status'] != remote_flow['attributes']['status']
                    and flow_without_status == remote_flow_without_status):
                flow_update_query = openapi_client.FlowUpdateQuery(data=resource_data)
                response = self.klaviyo.Flows.update_flow(flow_update_query.data.id, flow_update_query)
            else:
                click.secho(
                    'Changes to existing flows other than to the status attribute are unsupported. Skipping update.',
                    fg='red')
                return
        else:
            raise ValueError('Unsupported resource type.')
        clean_resource_data(resource_type, response['data'])
        self.write_data_to_file(resource_type, response['data'], resource_file)
        click.secho(f'Done writing updated {resource_type.value} definition to Klaviyo.', bold=True)

    def inspect_resource(self, resource_type, resource_path, resource_file, resource_id):
        resource_file = resource_filename(resource_type, resource_path, resource_file, resource_id)
        self.verbose_echo(
            f'Reading {resource_type.value} definition from {"stdin" if resource_file == "-" else resource_file}',
            bold=True)
        resource_data = read_resource_file(resource_file, resource_path)
        if resource_data is None:
            return
        table = Table(title=f'Properties of {resource_type.value}', highlight=True)
        table.add_column('Attribute')
        table.add_column('Value')
        if 'id' in resource_data:
            table.add_row('ID', resource_data['id'])
        if resource_type == ResourceType.SEGMENT:
            table.add_row('Name', resource_data['attributes']['name'])
            if 'created' in resource_data['attributes']:
                table.add_row('Created', resource_data['attributes']['created'])
            if 'starred' in resource_data['attributes']:
                table.add_row('Starred', resource_data['attributes']['starred'])
            table.add_row('Definition', json.dumps(resource_data['attributes']['definition'], indent=4))
        elif resource_type == ResourceType.UNIVERSAL_CONTENT_BLOCK:
            table.add_row('Name', resource_data['attributes']['name'])
            if 'created' in resource_data['attributes']:
                table.add_row('Created', resource_data['attributes']['created'])
            table.add_row('Definition', json.dumps(resource_data['attributes']['definition'], indent=4))
        elif resource_type == ResourceType.CAMPAIGN:
            table.add_row('Name', resource_data['attributes']['name'])
            if 'created' in resource_data['attributes']:
                table.add_row('Created', resource_data['attributes']['created'])
            table.add_row('Audiences', json.dumps(resource_data['attributes']['audiences'], indent=4))
            table.add_row('Tracking Options', json.dumps(resource_data['attributes']['tracking_options'], indent=4))
            table.add_row('Send Strategy', resource_data['attributes']['send_strategy']['method'])
        rich_console = Console()
        rich_console.print(table)

    def delete_resource(self, resource_type, resource_id):
        warning = click.style(f'Are you sure you want to delete {resource_type.value} {resource_id} from your Klaviyo account? This cannot be undone. ',
                              fg='red')
        click.confirm(warning, abort=True)
        if resource_type == ResourceType.SEGMENT:
            self.klaviyo.Segments.delete_segment(resource_id)
        elif resource_type == ResourceType.UNIVERSAL_CONTENT_BLOCK:
            self.klaviyo.Templates.delete_universal_content(resource_id)
        elif resource_type == ResourceType.CAMPAIGN:
            self.klaviyo.Campaigns.delete_campaign(resource_id)
        elif resource_type == ResourceType.FLOW:
            self.klaviyo.Flows.delete_flow(resource_id)
        else:
            raise ValueError('Unsupported resource type.')
        click.echo(f'Deleted {resource_type.value} {resource_id}.')

    def campaign_audience_prompt(self):
        """Prompts user to select the lists and segments to include and exclude from a campaign"""
        click.secho('Retrieving segments for audience selection...', bold=True)
        groups_data = self.get_all_pages(self.klaviyo.Segments.get_segments)
        click.secho('Retrieving lists for audience selection...', bold=True)
        groups_data += self.get_all_pages(self.klaviyo.Lists.get_lists)
        groups_table = Table(title='Choose groups to include in campaign audience', width=100)
        for parameter in ['ID', 'Type', 'Name', 'Created', 'Updated', '🌟']:
            groups_table.add_column(parameter, no_wrap=True, max_width=25)
        for group_data in groups_data:
            groups_table.add_row(group_data['id'], group_data['type'], group_data['attributes']['name'],
                                 group_data['attributes']['created'][:DATETIME_LENGTH],
                                 group_data['attributes']['updated'][:DATETIME_LENGTH],
                                 'Yes' if group_data['attributes'].get('is_starred') else 'No')
        included_indices = table_query_prompt(groups_table)
        groups_table.title = 'Choose groups to exclude from campaign audience'
        excluded_indices = table_query_prompt(groups_table)
        included = [groups_data[i]['id'] for i in included_indices]
        excluded = [groups_data[i]['id'] for i in excluded_indices]
        return {'included': included, 'excluded': excluded}


def resource_filename(resource_type: ResourceType, resource_path: str, resource_file: str | None, resource_id: str | None):
    """Returns the filename for a resource based on input options, or - for stdin if options are not provided"""
    if not resource_file:
        if resource_id:
            resource_file = os.path.join(resource_path, f'{resource_type.value}-{resource_id}.json')
        else:
            resource_file = '-'  # Read from stdin
    return resource_file


def read_resource_file(filename: str, resource_path: str = None):
    """Reads the contents of a resource definition file and returns the resource data. Returns None if file cannot be read"""
    if resource_path is not None:
        resource_path_filename = os.path.join(resource_path, filename)
        if os.path.exists(resource_path_filename):
            filename = resource_path_filename
    try:
        with click.open_file(filename, 'r') as f:
            resource_data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        click.secho(
            f'{format_filename(filename)} does not contain expected data format. Halting operation',
            fg='red')
        return None
    except FileNotFoundError:
        click.secho(f'File {format_filename(filename)} not found', fg='red')
        return None
    return resource_data


def campaign_send_strategy_prompt():
    """Prompts user to select the send strategy for a campaign"""
    send_strategy = {}
    methods = ['immediate', 'static', 'throttled', 'smart send time']
    send_strategy_method_index = survey.routines.select('Choose a send strategy: ',
                                                        options=['immediate', 'static', 'throttled',
                                                                 'smart send time'])
    send_strategy_method = methods[send_strategy_method_index]
    send_strategy['method'] = send_strategy_method.replace(' ', '_')
    if send_strategy_method in ('static', 'throttled'):
        send_strategy['datetime'] = survey.routines.datetime(
            'Choose when to send the campaign: ',
            attrs=('year', 'month', 'day', 'hour', 'minute', 'second'),
            date_delimit='-',
            value=datetime.datetime.now().replace(microsecond=0)
        ).isoformat()
    if send_strategy_method == 'static':
        is_local = survey.routines.select(
            'Should the campaign should be sent with local recipient timezone send? ',
            options=['Yes, send with local recipient timezone', 'No, send statically']
        ) == 0
        send_strategy['options'] = {'is_local': is_local}
        if is_local:
            send_past_immediately = survey.routines.select(
                'Should the campaign be sent to local recipients immediately if the time has passed? ',
                options=('Yes', 'No')
            ) == 0
            send_strategy['options']['send_past_recipients_immediately'] = send_past_immediately
    if send_strategy_method == 'throttled':
        send_strategy['throttle_percentage'] = survey.routines.numeric(
            'Enter the percentage of recipients per hour to send to: '
        )
    if send_strategy_method == 'smart send time':
        send_strategy['date'] = survey.routines.datetime(
            'Choose date to send the campaign: ',
            attrs=('year', 'month', 'day'),
            date_delimit='-',
            value=datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).date().isoformat()
    return send_strategy


def campaign_tracking_prompt(message_channel: str):
    """Prompts user to select the tracking options for a campaign"""
    tracking_options = {}
    tracking_params = ('custom', 'default', None)[survey.routines.select(
        'Should the campaign be sent with UTM tracking parameters? ',
        options=('Yes, send with custom UTM tracking parameters',
                 'Yes, send with company default UTM tracking parameters',
                 'No'))]
    add_tracking_params = tracking_params is not None
    custom_tracking_params = []
    prompt_for_tracking_params = (tracking_params == 'custom')
    while prompt_for_tracking_params:
        param_type = survey.routines.select('Tracking parameter type: ', options=['static', 'dynamic'])
        param_name = survey.routines.input('Tracking parameter name: ')
        param_value = survey.routines.input('Tracking parameter value: ')
        custom_tracking_params.append({
            'type': param_type,
            'name': param_name,
            'value': param_value
        })
        prompt_for_tracking_params = survey.routines.select('Do you have another tracking parameter to enter? ',
                                                            options=['Yes', 'No']) == 0
    tracking_options['add_tracking_params'] = add_tracking_params
    tracking_options['custom_tracking_params'] = custom_tracking_params
    if add_tracking_params and message_channel == 'email':
        is_tracking_clicks = [True, False, None][survey.routines.select(
            'Should the campaign track click events? ', options=['Yes', 'No', 'Use company defaults'])]
        if is_tracking_clicks is not None:
            tracking_options['is_tracking_clicks'] = is_tracking_clicks
        is_tracking_opens = [True, False, None][survey.routines.select(
            'Should the campaign track open events? ', options=['Yes', 'No', 'Use company defaults'])]
        if is_tracking_opens is not None:
            tracking_options['is_tracking_clicks'] = is_tracking_opens
    return tracking_options


def table_query_prompt(table: Table):
    """Prompts user to select rows from a table, returns indices"""
    rich_console = Console()
    with rich_console.capture() as capture:
        rich_console.print(table)
    rendered_table = capture.get().split('\n')
    table_header = '\n'.join([' ' * TABLE_INDENT + line for line in rendered_table[:TABLE_HEADER_HEIGHT]]) + '\n'
    table_footer = '\n'.join([' ' * TABLE_INDENT + line for line in rendered_table[-TABLE_FOOTER_HEIGHT:]])
    indices = survey.routines.basket(options=rendered_table[TABLE_HEADER_HEIGHT:-TABLE_FOOTER_HEIGHT], permit=True,
                                     show=table_header, search=table_search, reply=None)
    table_contents = [' ' * TABLE_INDENT + line for line in rendered_table[TABLE_HEADER_HEIGHT:-TABLE_FOOTER_HEIGHT]]
    for i in indices:
        click.echo(table_contents[i])
    click.echo(table_footer)
    return indices


def table_search(argument, tile, get=None):
    """Custom search for case-insensitive exact match of each word in filter string, see survey/survey/_searches.py"""
    lines, point = get(tile)
    line = ''.join(lines[0]).lower()
    arguments = ''.join(argument).lower().split(' ')
    if all(argument in line for argument in arguments):
        return 1
    return None


def style_prompt_string(message):
    """Formats a click prompt string to match the style of survey prompts"""
    return click.style('? ', fg='bright_yellow') + message


def format_filename(filename):
    return 'stdin stream' if filename == '-' else click.format_filename(filename)


def clean_resource_data(resource_type: ResourceType, resource_data: dict):
    """Remove fields from resource data that are not updatable or that may change in every response"""
    if resource_type == ResourceType.UNIVERSAL_CONTENT_BLOCK:
        del resource_data['attributes']['screenshot_url']
    elif resource_type == ResourceType.SEGMENT:
        del resource_data['attributes']['is_active']
        del resource_data['attributes']['is_processing']
    del resource_data['attributes']['updated']
