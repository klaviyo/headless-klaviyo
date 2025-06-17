
const vscode = require('vscode');

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
	console.log('The headless-klaviyo extension is now active');
}

function deactivate() {}

module.exports = {
	activate,
	deactivate
}
