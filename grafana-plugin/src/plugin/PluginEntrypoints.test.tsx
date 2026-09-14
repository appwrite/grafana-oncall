import React from 'react';

import { locationService } from '@grafana/runtime';
import { fireEvent, render, screen } from '@testing-library/react';
import { PLUGIN_CONFIG, PLUGIN_ROOT } from 'helpers/consts';

import { DemoNotification } from 'components/IntegrationSendDemoAlertModal/IntegrationSendDemoAlertModal';
import { MobileAppConnectionWrapper } from 'containers/MobileAppConnection/MobileAppConnection';

jest.mock('@grafana/runtime', () => {
  const { HistoryWrapper } = jest.requireActual('@grafana/runtime');
  return { locationService: new HistoryWrapper() };
});

jest.mock('helpers/hooks', () => ({
  ...jest.requireActual('helpers/hooks'),
  useInitializePlugin: () => ({ isConnected: false, isCheckingConnectionStatus: false }),
}));

jest.mock('state/rootStore', () => ({ rootStore: { userStore: {} } }));
jest.mock('components/MonacoEditor/MonacoEditor', () => ({ MonacoEditor: () => null }));

test('the disconnected profile extension renders and navigates without the plugin root', () => {
  window.grafanaBootData = { user: { orgRole: 'Admin' } } as typeof window.grafanaBootData;
  locationService.replace('/profile?tab=irm');
  render(<MobileAppConnectionWrapper />);
  expect(screen.getByText('Plugin not connected')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Open configuration' }));
  expect(locationService.getLocation().pathname).toBe(PLUGIN_CONFIG);
});

test('the demo alert toast renders its link in a separate Grafana root', () => {
  locationService.replace(`${PLUGIN_ROOT}/integrations/42`);
  render(<DemoNotification />);
  expect(screen.getByTestId('demo-alert-sent-notification')).toBeVisible();
  const link = screen.getByRole('link', { name: /Alert Groups/ });
  expect(link).toHaveAttribute('href', `${PLUGIN_ROOT}/alert-groups`);
  fireEvent.click(link);
  expect(locationService.getLocation().pathname).toBe(`${PLUGIN_ROOT}/alert-groups`);
});
