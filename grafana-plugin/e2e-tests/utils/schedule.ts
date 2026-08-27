import { expect, Locator, Page } from '@playwright/test';
import dayjs from 'dayjs';

import { clickButton, selectDropdownValue } from './forms';
import { goToOnCallPage } from './navigation';

export const createOnCallSchedule = async (
  page: Page,
  scheduleName: string,
  userName: string,
  withRotation = true
): Promise<void> => {
  // go to the schedules page
  await goToOnCallPage(page, 'schedules');

  // create an oncall-rotation schedule
  await clickButton({ page, buttonText: 'New Schedule' });
  await page.getByRole('button', { name: 'Create' }).first().click();

  // fill in the name input
  await page.getByTestId('schedule-form').locator('input[name="name"]').fill(scheduleName);

  // Add a new layer w/ the current user to it
  await clickButton({ page, buttonText: 'Create Schedule' });

  if (withRotation) {
    await createRotation(page, userName);
  }
};

export const createRotation = async (page: Page, userName: string, isFirstScheduleRotation = true) => {
  await clickButton({ page, buttonText: 'Add rotation' });
  if (!isFirstScheduleRotation) {
    await page.getByText('Layer 1 rotation', { exact: true }).click();
  }
  await selectDropdownValue({
    page,
    selectType: 'grafanaSelect',
    placeholderText: 'Add user',
    value: userName,
  });
  await clickButton({ page, buttonText: 'Create' });
};

export interface OverrideFormDateInputs {
  start: dayjs.Dayjs;
  end: dayjs.Dayjs;
}

export const getOverrideFormDateInputs = async (page: Page): Promise<OverrideFormDateInputs> => {
  const getInputValue = async (inputNumber: number): Promise<string> => {
    const element = await page.waitForSelector(`div[data-testid=\"override-inputs\"] >> input >> nth=${inputNumber}`);
    return await element.inputValue();
  };

  const startDate = await getInputValue(0);
  const startTime = await getInputValue(1);

  const endDate = await getInputValue(2);
  const endTime = await getInputValue(3);

  const startDateTime = dayjs(`${startDate} ${startTime}`, 'MM/DD/YYYY HH:mm');
  const endDateTime = dayjs(`${endDate} ${endTime}`, 'MM/DD/YYYY HH:mm');

  return {
    start: startDateTime,
    end: endDateTime,
  };
};

/**
 * Grafana renders the time picker differently per major version — a typeable input in 12,
 * a combobox in 13 — so target the input itself rather than a role, and type instead of
 * clicking through the panel.
 */
export const getTimeInput = (element: Locator) => element.getByTestId('date-time-picker').locator('input');

export const setTime = async (element: Locator, hour: string) => {
  await typeTime(getTimeInput(element), `${hour}:00`);
};

/**
 * Grafana 12 takes a typed time; 13 renders a combobox that only commits a value picked from its
 * list, so type first and correct it from the list when the typing did not stick.
 */
export const typeTime = async (input: Locator, value: string) => {
  // fill focuses and replaces the value in one action. Separate click/clear/type actions race with
  // the controlled combobox remount introduced in Grafana 13.2.
  await input.fill(value);

  // grafana 13 renders a combobox that only commits a value picked from its list; 12 takes the
  // typed value on Enter. Don't click the input again here — that would close the open list.
  const option = input.page().getByRole('option', { name: value, exact: true }).first();

  try {
    await option.waitFor({ state: 'visible', timeout: 1_000 });
    await option.click();
  } catch {
    await input.press('Enter');
  }

  // Grafana 12 can occasionally discard fill() updates when the controlled input rerenders.
  // Retry with real key events in that case; Grafana 13 normally commits through the option above.
  if ((await input.inputValue()) !== value) {
    await input.click();
    await input.fill('');
    await input.pressSequentially(value);
    await input.press('Enter');
  }

  await expect(input).toHaveValue(value);
};

/** the open menu of a grafana Select, which is portalled out of its container */
export const getSelectMenu = (page: Page) => page.locator('div[id^="react-select-"][id$="-listbox"]');
