# Headless Klaviyo CLI
The Headless Klaviyo command line interface offers a way to manage Klaviyo campaigns, flows, segments, and universal content blocks through the command line and as files. For guidance on other tools developers can use to manage their Klaviyo resources, see the [Klaviyo Developer Portal](https://developers.klaviyo.com/).

## Setup

### Install pipx

If you don't have it installed already, install `pipx`

#### On macOS

```bash
brew install pipx
pipx ensurepath
```

#### On Linux

```bash
sudo apt update
sudo apt install pipx
pipx ensurepath
```

#### On Windows

```bash
scoop install pipx
pipx ensurepath
```

For more information, including instructions on how to install `pipx` using `pip`, refer to the [pipx installation guide](https://pipx.pypa.io/stable/installation/).

### Install the Klaviyo CLI

Use `pipx` to install the Klaviyo CLI:

```bash
pipx install headless-klaviyo
```

Test that the `klaviyo` command can now be used:

```bash
klaviyo --help
```

# Basic usage

The command is invoked by entering `klaviyo` followed by a subcommand name and the relevant options for that subcommand.

If you aren't sure what options and arguments to specify for a subcommand, use the --help option for that command. For example, to see the available options for the `get campaigns` subcommand, enter:

```bash
klaviyo get campaigns --help
```

Commands require a private API key to authenticate requests to Klaviyo. See [how to create a private API key](https://help.klaviyo.com/hc/en-us/articles/7423954176283) for information.

**The recommended way to configure your API key is to run the `set api-key` command:**

```bash
klaviyo set api-key
```

This will prompt you for your key and save it to a `.env` file in your current directory. The CLI will automatically use this key for all future commands.

Alternatively, the API key can be specified for a single command with the `--api-key` option or by setting the `KLAVIYO_API_KEY` environment variable.

Example command using the `--api-key` option:

```bash
klaviyo get campaigns --overwrite-mode keep-local --api-key pk_0000
```

# Command listing

The following examples assume that you have set the `KLAVIYO_API_KEY` using the `klaviyo set api-key` command or by setting the `KLAVIYO_API_KEY` environment variable.

## `get`

The `get` command retrieves resource definitions from Klaviyo and stores them to local files.

Retrieve an individual file with the `block`, `campaign`, `flow` and `segment` subcommands. These commands should be followed by the ID of the resource to retrieve.

For example, to retrieve the definition of the segment with ID `R6qs5F`, use the following command:

```bash
klaviyo get segment R6qs5F
```

This command will save the segment definition to a subfolder of the working directory named `segments` by default. This can be changed using the `--segment-path` option, or the equivalent for the other resource types.

By default, you will be prompted to confirm that you would like to overwrite an existing file if one exists. You can change this behavior with the `--overwrite-mode` option.

For example, the following command retrieves the segment to the file `resources/segments/segment-R6qs5F.json`, and overwrites that file if it already exists without asking for confirmation.

```bash
klaviyo get segment R6qs5F --overwrite-mode overwrite --segment-path resources/segments
```

Use the `--stdout` flag to indicate that the `get` command should print the retrieved definition to STDOUT, and should suppress all other output. See the [Usage examples](#additional-usage-examples) section below for examples of how to use this in combination with other commands.

You can retrieve all resources of a type at once using the plural versions of the subcommands: `blocks`, `campaigns`, `flows` and `segments`. These commands support all options that the singular versions do, and do not require a specified resource ID.

If you want to retrieve all four supported resource types, use the `all` subcommand. To request informative output related to each created or modified file, use the `--verbose` flag, as follows:

```bash
klaviyo get all --verbose
```

## `set`

The `set` command configures settings for the CLI.

### `set api-key`

This command securely prompts for your Klaviyo private API key and saves it to a `.env` file in the current working directory. This is the recommended way to configure authentication, as you will not need to provide the key with every command.

```bash
klaviyo set api-key
```

You will be prompted to enter your API key, and the input will be hidden for security.

## `inspect`

The `inspect` command outputs a table with information about a resource based on a local resource definition file. The supported subcommands are `block`, `campaign`, `flow`, and `segment`.

The file to inspect can be specified with the relevant file or ID command options. For example, the following are equivalent ways to inspect the flow definition stored in the file `flows/flow-QWEbek.json`:

```bash
klaviyo inspect flow --flow-id QWEbek
klaviyo inspect flow --flow-file flow-QWEbek.json
```

If neither of these options is specified, the command will read in a definition from `STDIN`.

The folder that stores the definition files can be specified using the relevant path option (e.g. `--flow-path`).

## `generate`

The `generate` command creates a local resource definition file for a new resource. The supported subcommands are `campaign`, `profile` and `block`.

These commands will prompt you for parameters that are not provided as command options. For example, the following command will create a campaign definition file with the name attribute "Test Campaign", and then will interactively prompt you to select the lists and segments to use for the campaign audience from those that exist in your Klaviyo account, the campaign send strategy, and other parameters:

```bash
klaviyo generate campaign --name "Test Campaign"
```

Once a resource definition file is created with the `generate` command, it can be edited further with the text editor of your choice. Once edited, use it to create a resource with the `create` command.

Newly-created resources may require additional steps to utilize. For example, a template must be attached to an email campaign and its status updated to live. See the [Campaigns API](https://developers.klaviyo.com/en/reference/campaigns_api_overview) and [Universal Content API](https://developers.klaviyo.com/en/reference/universal_content_api_overview) overviews for more information.

## `create`

The `create` command creates a new Klaviyo resource based on a local definition file. The supported subcommands are `block`, `profile`, `campaign`, `flow`, and `segment`.

The file is specified with the `--segment-file` option for segments, and the equivalent for other resource types. After creating the resource, the result will be saved to a new file with its assigned ID in the specified resource path (e.g. for a segment, the path specified with `--segment-path`, default `segments`).

Example creation of a segment based on a definition file named `new_segment_1.json` in the `segments` path:

```bash
klaviyo create segment --segment-file new_segment_1.json
```

The definition file used to create a resource must not already have an ID. If no file option is specified, the command will read from `STDIN`.

## `update`

The `update` command updates an existing Klaviyo resource to match a local resource definition. The supported subcommands are `block`, `campaign`, `flow`, and `segment`. Note that `flow` resources are only partially supported. Only the `status` attribute for existing flows can be edited, not other flow attributes.

The file can be specified with either the relevant file or ID parameters, for example `--campaign-file` or `--campaign-id` for campaigns. If neither is specified, the command will read the definition in from `STDIN`.

## `delete`

The `delete` command deletes a Klaviyo resource. The supported subcommands are `block`, `campaign`, `flow`, and `segment`.

The subcommand name should be followed by the resource ID of the resource to delete. This removes the resource from your Klaviyo account, and does not modify or delete local definition files. You will be prompted with a warning before the resource is deleted.

> Warning: this operation cannot be undone.

To delete the segment with ID `R6qs5F`:

```bash
klaviyo delete segment R6qs5F
```

## `report`

The `report` command creates a report about a Klaviyo resource. The supported subcommands are `campaign`, `flow`, `form`, and `segment`.

The subcommand name should be followed by the resource ID of the resource to report on. These commands will prompt you for parameters that are not provided as command options. For example, the following command will create a report about the campaign with ID `01J9SCZKEP89D14YCP2X97CZZ1` over the last 12 months, and will interactively prompt you to select the statistics for the report, as well as the metric used to calculate conversion statistics:

```bash
klaviyo report campaign 01J9SCZKEP89D14YCP2X97CZZ1 --timeframe last_12_months
```

The report output will be stored as a CSV (Comma Separated Values) file including the selected statistics, and for series reports, the timestamps for each interval. The folder to use to store the reports can be specified with the `--report-path` option. The output file name will include the timestamp of the report creation, and new reports will create new files rather than overwrite existing reports.

## About resource definition files

The resource definition files stored by these commands generally match the format of the `data` section of the `json:api` payload used for interacting with the Klaviyo API. For specifics on the formats of these resource definitions, refer to the [Klaviyo API documentation](https://developers.klaviyo.com/en/reference/). For example, the `campaign` data model is described in the [Campaigns API overview](https://developers.klaviyo.com/en/reference/campaigns_api_overview).

One minor difference is that the resource definition files created through this CLI exclude some information that changes every time the API is called, such as the screenshot URL for universal content blocks and the `updated` date for all resource types.

# Additional usage examples

Here are some additional examples of how you can use these commands in combination. Note that the specific ways to accomplish these tasks may vary based on your operating system.

The `get` command with the `--stdout` flag can be used to compare a remote resource definition to the local version by piping it into the `diff` command. The following compares the remote version of the segment `R6qs5F` to an existing local definition file:

```bash
klaviyo get segment R6qs5F --stdout | diff - segments/segment-R6qs5F.json
```

You can also inspect a remote resource without saving it first by piping the output of the `get` command into the `inspect` command:

```bash
klaviyo get segment R6qs5F --stdout | klaviyo inspect segment
```

If you would like to create a new resource that is a copy of an existing resource, copy that resource definition file, rename the copied file, remove the line in the file that specifies the ID, and use the new file with `klaviyo create`. Alternatively, as a combination of commands:

```bash
cat segments/segment-R6qs5F.json | sed '/"id": /d' | klaviyo create segment
```

# GitHub actions
If you are interested in managing changes to resource definitions files with GitHub pull requests, there is a GitHub action available to do so. See the readme [here](github_actions/README.md) for more information.

# Development setup

If you want to make changes to the program or contribute changes, you can set it up for local development.

Clone this project to your local machine, then build it with the following command:

```bash
python -m build
```

Next, install the generated `whl` file. Note that the exact file name may differ. To confirm the file name, check the output of the build command.

```bash
pip install dist/headless_klaviyo-0.1.0-py3-none-any.whl
```

Use the `--force-reinstall` flag if you've previously installed the package.

# Contributing

We welcome contributions from the community! If you'd like to contribute, please follow these steps:

1. Fork the repository and create a new branch for your changes.
2. Make your changes. Do your best to have your changes match the existing structure and style.
3. Submit a pull request (PR) with a clear description of your changes.
4. Wait for review – we'll provide feedback and merge once it's ready!

You can also report any bugs you find by opening an issue in this GitHub repo.
