import { test, expect } from '../fixtures';
import { goToOnCallPage } from '../utils/navigation';
import { verifyThatUserCanViewOtherUsers, accessProfileTabs } from '../utils/users';

test.describe('Users screen actions', () => {
  test('Viewer is not allowed to view the list of users', async ({ viewerRolePage: { page } }) => {
    await verifyThatUserCanViewOtherUsers(page, false);
  });

  test('Viewer cannot access restricted tabs from View My Profile', async ({ viewerRolePage }) => {
    const { page } = viewerRolePage;
    // tab-mobile-app lives in the global user profile, not here
    const tabsToCheck = ['tab-phone-verification', 'tab-slack', 'tab-telegram'];

    await accessProfileTabs(page, tabsToCheck, false);
  });

  test('Editor is allowed to view the list of users', async ({ editorRolePage }) => {
    await verifyThatUserCanViewOtherUsers(editorRolePage.page);
  });

  test("Editor cannot view other users' data", async ({ editorRolePage }) => {
    const { page } = editorRolePage;

    await goToOnCallPage(page, 'users');
    await page.getByTestId('users-email').and(page.getByText('editor')).waitFor();

    await expect(page.getByTestId('users-email').and(page.getByText('editor'))).toHaveCount(1);
    const maskedEmails = page.getByTestId('users-email').and(page.getByText('******'));
    const maskedPhoneNumbers = page.getByTestId('users-phone-number').and(page.getByText('******'));
    await expect.poll(() => maskedEmails.count()).toBeGreaterThan(1);
    await expect.poll(() => maskedPhoneNumbers.count()).toBeGreaterThan(1);
  });

  test('Editor can access tabs from View My Profile', async ({ editorRolePage }) => {
    const { page } = editorRolePage;

    // the other tabs depend on Cloud, skip for now
    await accessProfileTabs(page, ['tab-slack', 'tab-telegram'], true);
  });

  test("Editor is not allowed to edit other users' profile", async ({ editorRolePage: { page } }) => {
    await goToOnCallPage(page, 'users');
    await expect(page.getByTestId('users-table').getByRole('button', { name: 'Edit', disabled: false })).toHaveCount(1);
    const usersWithDisabledEdit = page.getByTestId('users-table').getByRole('button', { name: 'Edit', disabled: true });
    await expect.poll(() => usersWithDisabledEdit.count()).toBeGreaterThan(1);
  });

  test("Admin is allowed to edit other users' profile", async ({ adminRolePage: { page } }) => {
    await goToOnCallPage(page, 'users');
    const editableUsers = page.getByTestId('users-table').getByRole('button', { name: 'Edit', disabled: false });
    await expect.poll(() => editableUsers.count()).toBeGreaterThan(1);
  });

  test('Admin is allowed to view the list of users', async ({ adminRolePage: { page } }) => {
    await verifyThatUserCanViewOtherUsers(page);
  });

  test('Search updates the table view', async ({ adminRolePage }) => {
    const { page, userName } = adminRolePage;
    await goToOnCallPage(page, 'users');

    await page.waitForTimeout(2000);

    await page
      .locator('div')
      .filter({ hasText: /^Search or filter results\.\.\.$/ })
      .nth(1)
      .click();
    await page.keyboard.insertText(userName);
    await page.keyboard.press('Enter');

    // polls until the search has filtered the table, rather than sleeping and reading once
    await expect(page.locator(`[data-testid="users-username"]`)).toHaveCount(1);
  });
});
