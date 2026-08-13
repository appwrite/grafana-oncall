import { PLUGIN_CONFIG } from 'helpers/consts';

import { test, expect } from '../fixtures';
import { goToGrafanaPage } from '../utils/navigation';

test.describe('Plugin configuration', () => {
  test('Admin user can see currently applied URL', async ({ adminRolePage: { page } }) => {
    await goToGrafanaPage(page, PLUGIN_CONFIG);

    // the plugin config page takes a while to hydrate on grafana 13
    await expect(page.getByTestId('oncall-api-url-input')).toHaveValue('http://oncall-dev-engine:8080', {
      timeout: 15_000,
    });
  });

  test('Admin user can see error when invalid OnCall API URL is entered and plugin is reconnected', async ({
    adminRolePage: { page },
  }) => {
    await goToGrafanaPage(page, PLUGIN_CONFIG);

    // the input is populated once the plugin settings load
    const urlInput = page.getByTestId('oncall-api-url-input');
    await expect(urlInput).not.toHaveValue('', { timeout: 15_000 });
    const correctURLAppliedByDefault = await urlInput.inputValue();

    // show client-side validation errors
    await urlInput.fill('');
    await page.getByText('URL is required').waitFor();
    await urlInput.fill('invalid-url-format:8080');
    await page.getByText('URL is invalid').waitFor();

    // apply back correct url and verify plugin connected again
    await urlInput.fill(correctURLAppliedByDefault);

    // the button stays disabled until the form revalidates
    const connectPlugin = page.getByTestId('connect-plugin');
    await expect(connectPlugin).toBeEnabled();
    await connectPlugin.click();

    await page.getByText('Plugin is connected').waitFor();
  });
});
