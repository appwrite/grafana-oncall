import { test, expect } from '../fixtures';
import { MOSCOW_TIMEZONE } from '../utils/constants';
import { clickButton, generateRandomValue } from '../utils/forms';
import { setTimezoneInProfile } from '../utils/grafanaProfile';
import { createOnCallSchedule, getTimeInput, setTime } from '../utils/schedule';

test('Fills in Rotation time and  reacts to timezone change', async ({ adminRolePage }) => {
  const { page, userName } = adminRolePage;

  await setTimezoneInProfile(page, MOSCOW_TIMEZONE); // UTC+3

  const onCallScheduleName = generateRandomValue();
  await createOnCallSchedule(page, onCallScheduleName, userName, false);

  await clickButton({ page, buttonText: 'Add rotation' });
  // enable Rotation End
  await page.getByTestId('rotation-end').getByRole('switch').click();

  const startEl = page.getByTestId('rotation-start');
  await setTime(startEl, '02');
  await expect(getTimeInput(startEl)).toHaveValue('02:00');

  const endEl = page.getByTestId('rotation-end');
  await setTime(endEl, '12');
  await expect(getTimeInput(endEl)).toHaveValue('12:00');

  await page.getByRole('dialog').click(); // clear focus

  await page.getByTestId('timezone-select').locator('svg').click();
  await page.getByText('GMT', { exact: true }).click();

  // expect times to go back by -3
  await expect(getTimeInput(startEl)).toHaveValue('23:00');
  await expect(getTimeInput(endEl)).toHaveValue('09:00');

});
