import { test, expect } from '../fixtures';
import { generateRandomValue } from '../utils/forms';
import { createOnCallSchedule, createRotation } from '../utils/schedule';

test(`user can see the other user's details`, async ({ adminRolePage, editorRolePage }) => {
  const { page, userName: adminUserName } = adminRolePage;
  const editorUserName = editorRolePage.userName;
  const onCallScheduleName = generateRandomValue();

  await createOnCallSchedule(page, onCallScheduleName, adminUserName);
  await createRotation(page, editorUserName, false);

  // both rotations sit in the same layer, so hover the editor's avatar rather than whichever one
  // happens to render first. The locator waits for it, so no fixed sleep is needed either.
  await page
    .getByTestId('user-avatar-in-schedule')
    .filter({ has: page.getByAltText(editorUserName, { exact: true }) })
    .hover();
  await expect(page.getByTestId('schedule-user-details')).toHaveText(new RegExp(editorUserName));
});
