import { KeyValue } from '@grafana/data';
import type { Page } from '@playwright/test';
import { getPluginId } from 'helpers/consts';
import { stringifyQuery } from 'helpers/query';

import { BASE_URL } from './constants';

type OnCallPage =
  | 'alert-groups'
  | 'integrations'
  | 'escalations'
  | 'schedules'
  | 'outgoing_webhooks'
  | 'users'
  | 'users/me'
  | 'insights'
  | 'settings';

const _goToPage = async (page: Page, url = '') => page.goto(`${BASE_URL}${url}`);

export const goToGrafanaPage = async (page: Page, url = '') => _goToPage(page, url);

export const goToOnCallPage = async (page: Page, onCallPage: OnCallPage, queryParams?: KeyValue) => {
  const queryParamsString = queryParams ? `?${stringifyQuery(queryParams)}` : '';
  await _goToPage(page, `/a/${getPluginId()}/${onCallPage}${queryParamsString}`);
  // no networkidle wait: grafana 13 keeps connections open, so it never settles
  await page.waitForTimeout(1000);
};
