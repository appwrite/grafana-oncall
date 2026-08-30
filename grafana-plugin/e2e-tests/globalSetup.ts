import {
  test as setup,
  expect,
  chromium,
  type BrowserContext,
  type FullConfig,
  type APIRequestContext,
  Page,
} from '@playwright/test';

import { VIEWER_USER_STORAGE_STATE, EDITOR_USER_STORAGE_STATE, ADMIN_USER_STORAGE_STATE } from '../playwright.config';

import grafanaApiClient from './utils/clients/grafana';
import {
  GRAFANA_ADMIN_PASSWORD,
  GRAFANA_ADMIN_USERNAME,
  GRAFANA_EDITOR_PASSWORD,
  GRAFANA_EDITOR_USERNAME,
  GRAFANA_VIEWER_PASSWORD,
  GRAFANA_VIEWER_USERNAME,
  IS_CLOUD,
  IS_OPEN_SOURCE,
  OrgRole,
} from './utils/constants';
import { goToOnCallPage } from './utils/navigation';

type UserCreationSettings = {
  adminAuthedRequest: APIRequestContext;
  role: OrgRole;
};

const generateLoginStorageStateAndOptionallCreateUser = async (
  config: FullConfig,
  userName: string,
  password: string,
  storageStateFileLocation: string,
  userCreationSettings?: UserCreationSettings,
  closeContext = false
): Promise<BrowserContext> => {
  if (userCreationSettings !== undefined && IS_OPEN_SOURCE) {
    const { adminAuthedRequest, role } = userCreationSettings;
    await grafanaApiClient.idempotentlyCreateUserWithRole(adminAuthedRequest, userName, password, role);
  }

  const { headless } = config.projects[0]!.use;
  const browser = await chromium.launch({ headless, slowMo: headless ? 0 : 100 });
  const browserContext = await browser.newContext();

  await grafanaApiClient.login(browserContext.request, userName, password);
  await browserContext.storageState({ path: storageStateFileLocation });

  if (closeContext) {
    await browserContext.close();
  }
  return browserContext;
};

const idempotentlyInitializePlugin = async (page: Page) => {
  await goToOnCallPage(page, 'alert-groups');
  const openPluginConfigurationButton = page.getByRole('button', { name: 'Open configuration' });

  // Grafana 13 can take longer than the navigation helper's initial delay to
  // finish checking the plugin connection. Wait for either terminal state.
  await expect(openPluginConfigurationButton.or(page.getByTestId('page-title'))).toBeVisible({ timeout: 30_000 });

  if (await openPluginConfigurationButton.isVisible()) {
    await openPluginConfigurationButton.click();
    await page.getByTestId('connect-plugin').click();
    await page.waitForLoadState('networkidle');
    await page.getByText('Plugin is connected').waitFor();
  }
};

/**
 * Borrowed from our friends on the Incident team
 * https://github.com/grafana/incident/blob/main/plugin/e2e/global-setup.ts
 */
setup('Configure Grafana OnCall plugin', async ({ request }, { config }) => {
  if (IS_CLOUD) {
    await grafanaApiClient.pollInstanceUntilItIsHealthy(request);
  }

  const adminBrowserContext = await generateLoginStorageStateAndOptionallCreateUser(
    config,
    GRAFANA_ADMIN_USERNAME,
    GRAFANA_ADMIN_PASSWORD,
    ADMIN_USER_STORAGE_STATE
  );
  const adminPage = await adminBrowserContext.newPage();
  const { request: adminAuthedRequest } = adminBrowserContext;

  await idempotentlyInitializePlugin(adminPage);

  await generateLoginStorageStateAndOptionallCreateUser(
    config,
    GRAFANA_EDITOR_USERNAME,
    GRAFANA_EDITOR_PASSWORD,
    EDITOR_USER_STORAGE_STATE,
    {
      adminAuthedRequest,
      role: OrgRole.Editor,
    },
    true
  );

  await generateLoginStorageStateAndOptionallCreateUser(
    config,
    GRAFANA_VIEWER_USERNAME,
    GRAFANA_VIEWER_PASSWORD,
    VIEWER_USER_STORAGE_STATE,
    {
      adminAuthedRequest,
      role: OrgRole.Viewer,
    },
    true
  );

  await adminBrowserContext.close();
});
