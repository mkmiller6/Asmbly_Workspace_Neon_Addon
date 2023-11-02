# Asmbly Workspace Integrations

This Google Workspace add-on allows users within the Asmbly domain to perform common tasks within Neon and Openpath 
without needing to leave Gmail. The goal is to reduce context switching and thus speedup routine tasks.

Actions within the add-on are split into contextual and non-contextual categories. Contextual actions are available
when the user has an email open. The add-on will determine the Neon/OP account based on the email address of the open
email. Non-contextual actions are available without any emails open.

Capabilites of the add-on include:

- Contextual:
    - Checking the access requirements of the user
    - Manually running the Openpath update script for that user
    - Retrieving the Neon ID of the user for subsequent use in the Neon UI if needed
    - Registering the user for classes with a $0 registration
    - Canceling and refunding a user's registration for an upcoming class
- Non-contextual:
    - Checking the access requirements of any user via the input Neon ID or email address
    - Updating a user's Openpath access based on Neon ID or email address
    - Looking up the purchaser of a gift certificate by gift certificate number
    - One-click CCing of the membership alias when composing emails

## Add-on Installation and Setup

The add-on can be installed via the [Google Workspace Marketplace](https://workspace.google.com/marketplace/) 
under the "Internal apps" section in the left sidebar.

Once the add-on is installed, it can be accessed via the right sidebar in Gmail by clicking the Asmbly logo.

The user of the add-on will need to add their API keys on the add-on settings page. To perform most actions, the user 
will need to input their Neon API key. Additionally, to use the Openpath update features, the user must input their 
Openpath API key and user info. If you don't have Neon or Openpath API keys or don't know how to get them, send a 
message in #staff-questions on Slack. 

## Code Documentation

This add-on is built with [FastAPI](https://fastapi.tiangolo.com) and run on 
[Google Cloud Run](https://cloud.google.com/run/docs/overview/what-is-cloud-run). 
The container image, built with the included Dockerfile, is stored in 
[Google Artifact Registry](https://cloud.google.com/artifact-registry/docs). All API keys are stored securely in 
[Google Secret Manager](https://cloud.google.com/secret-manager/docs).

Google has excellent [documentation](https://developers.google.com/workspace/add-ons/guides/alternate-runtimes) 
on building Google Workspace Add-ons in alternate runtimes (i.e. not in Google Apps Script). To help facilitate 
returning properly formatted JSON cards, this project uses a modified version of the 
[GAPPS package](https://github.com/skoudoro/gapps).