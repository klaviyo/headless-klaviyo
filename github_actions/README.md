# GitHub Action for managing Klaviyo resources with GitHub
The `sync` GitHub action defined in `update-klaviyo-resources.yml` offers a method to update Klaviyo resources based on new and updated resource definition files merged via pull request into a GitHub repository.
This may be useful if you would like to use GitHub for version control and the pull request process for managing changes to the definitions of campaigns, flows, segments, and universal content blocks.

For information on the Klaviyo CLI and resource definition format used by this action, see the [Klaviyo CLI developer guide](https://developers.klaviyo.com/en/docs/klaviyo_cli).

## Setup
1. Create a GitHub repository for the resource definitions associated with your Klaviyo account.
   You can populate these definitions by running `klaviyo get all` with the [Klaviyo CLI](https://developers.klaviyo.com/en/docs/klaviyo_cli) installed and with the `KLAVIYO_API_KEY` environment variable assigned to a private API key associated with that account. 
   The action expects the default folder structure used by the Klaviyo CLI, with resource definitions for blocks, campaigns, flows, and segments each stored in a subfolder of the repository root directory.
2. Place the `update-klaviyo-resources.yml` file in the `.github/workflows` folder in the repository. By default, this workflow acts on pull requests merged into the `main` git branch. If your main branch has a different name, edit the workflow to match that branch name.
3. Configure a GitHub repository secret named `KLAVIYO_API_KEY` that contains an API key associated with your account.
   > :warning: **This will allow users with contributor-level access to your repository to use GitHub actions to make changes to your Klaviyo account.**
   >
   > Ensure that contributor-level access is limited to users that should have this permission, that the key is saved as a secret and not as a variable, and follow [guidance on keeping your account secure](https://help.klaviyo.com/hc/en-us/articles/360052448451).

## Usage
### Create new resources
To create a new resource, merge a pull request containing a new resource definition file into the `main` branch of the repository.
For example, creating and merging a pull request that adds a valid campaign resource definition file named `campaigns/new_campaign_1.json` to the `main` branch will result in that Klaviyo campaign being created.

Once that resource is created, the version of the resource definition with its assigned Klaviyo ID will be retrieved and automatically pushed to the `main` branch.
The template file (in this case `new_campaign_1.json`) will not be automatically deleted. If you no longer plan to use that template, it can be manually deleted and removed from the repository.

### Update existing resources
To update a Klaviyo resource, merge a pull request containing a change to that resource's definition file to the `main` branch of the repository.

### Other usage notes
* Any number of new additions and changes can be made in a single pull request, and all of them will be processed by the GitHub action.
* In order to prevent the inadvertent deletion of Klaviyo resources, deleting a resource from the repository does not delete that resource from Klaviyo. Resources can be manually deleted with the Klaviyo CLI.
* This GitHub action only makes changes to Klaviyo resources based on new and edited resource definitions in the repository. It will not automatically retrieve changes and new resources created outside the repository.
