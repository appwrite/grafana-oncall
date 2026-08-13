import dayjs from 'dayjs';

import { test, expect } from '../fixtures';
import { MOSCOW_TIMEZONE } from '../utils/constants';
import { clickButton, generateRandomValue } from '../utils/forms';
import { setTimezoneInProfile } from '../utils/grafanaProfile';
import { createOnCallSchedule, getOverrideFormDateInputs, getTimeInput, setTime } from '../utils/schedule';

test('Default dates in override creation modal are set to today', async ({ adminRolePage }) => {
  const { page, userName } = adminRolePage;

  const onCallScheduleName = generateRandomValue();
  await createOnCallSchedule(page, onCallScheduleName, userName);

  await page.clock.setFixedTime(new Date().setHours(12, 0, 0, 0));
  await page.getByTestId('timezone-select').locator('svg').click();
  await page.getByRole('option').getByText(/^GMT$/).click();

  await clickButton({ page, buttonText: 'Add override' });

  const overrideFormDateInputs = await getOverrideFormDateInputs(page);

  const expectedStart = dayjs().startOf('day'); // start of today
  const expectedEnd = expectedStart.add(1, 'day'); // end of today

  expect(overrideFormDateInputs.start.isSame(expectedStart)).toBe(true);
  expect(overrideFormDateInputs.end.isSame(expectedEnd)).toBe(true);
});

test('Fills in override time and reacts to timezone change', async ({ adminRolePage }) => {
  const { page, userName } = adminRolePage;

  await setTimezoneInProfile(page, MOSCOW_TIMEZONE); // UTC+3

  const onCallScheduleName = generateRandomValue();
  await createOnCallSchedule(page, onCallScheduleName, userName, false);

  await clickButton({ page, buttonText: 'Add override' });

  const overrideStartEl = page.getByTestId('override-start');
  await setTime(overrideStartEl, '02');
  await expect(getTimeInput(overrideStartEl)).toHaveValue('02:00');

  const overrideEndEl = page.getByTestId('override-end');
  await setTime(overrideEndEl, '12');
  await expect(getTimeInput(overrideEndEl)).toHaveValue('12:00');

  await page.getByRole('dialog').click(); // clear focus

  await page.getByTestId('timezone-select').locator('svg').click();
  await page.getByText('GMT', { exact: true }).click();

  // expect times to go back by -3
  await expect(getTimeInput(overrideStartEl)).toHaveValue('23:00');
  await expect(getTimeInput(overrideEndEl)).toHaveValue('09:00');

});
