import { Page, expect } from '@playwright/test';

import { BASE_URL } from './constants';

/**
 * Set through the API rather than the profile page: the timezone is a precondition for the
 * schedule tests, not the thing under test, and grafana keeps rewriting the picker (each major
 * labels its options differently). page.request shares the browser's session cookies.
 */
export const setTimezoneInProfile = async (page: Page, timezone: string) => {
  const response = await page.request.patch(`${BASE_URL}/api/user/preferences`, { data: { timezone } });

  expect(response.ok()).toBeTruthy();
};
