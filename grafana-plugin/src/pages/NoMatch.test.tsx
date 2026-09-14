import React from 'react';

import { locationService } from '@grafana/runtime';
import { render, screen } from '@testing-library/react';
import { DEFAULT_PAGE, PLUGIN_ROOT } from 'helpers/consts';
import { Route, Routes, useParams } from 'react-router-v7';

import { PluginRouter } from 'plugin/PluginRouter';

import { NoMatch } from './NoMatch';

jest.mock('@grafana/runtime', () => {
  const { HistoryWrapper } = jest.requireActual('@grafana/runtime');
  return { locationService: new HistoryWrapper() };
});

function IncidentDestination() {
  const { id } = useParams();
  return <h1>Incident {id}</h1>;
}

function openLegacyUrl(search: string) {
  window.history.replaceState(null, '', `${PLUGIN_ROOT}${search}`);
  locationService.replace(`${PLUGIN_ROOT}${search}`);
  render(
    <PluginRouter>
      <Routes>
        <Route path={`${PLUGIN_ROOT}/incidents/:id`} element={<IncidentDestination />} />
        <Route path={`${PLUGIN_ROOT}/${DEFAULT_PAGE}`} element={<h1>Alert groups</h1>} />
        <Route path="*" element={<NoMatch />} />
      </Routes>
    </PluginRouter>
  );
}

afterEach(() => window.history.replaceState(null, '', '/'));

test('a legacy incident bookmark opens the incident and retains its filters', () => {
  openLegacyUrl('?page=incident&id=42&search=caf%C3%A9+%26+cpu&team=one&team=two&flag');
  expect(screen.getByRole('heading', { name: 'Incident 42' })).toBeInTheDocument();
  expect(locationService.getLocation().pathname).toBe(`${PLUGIN_ROOT}/incidents/42`);
  expect(locationService.getLocation().search).toBe('?flag&search=caf%C3%A9%20%26%20cpu&team=one&team=two');
});

test('opening the plugin without a page shows the default alert groups page', () => {
  openLegacyUrl('');
  expect(screen.getByRole('heading', { name: 'Alert groups' })).toBeInTheDocument();
  expect(locationService.getLocation().pathname).toBe(`${PLUGIN_ROOT}/${DEFAULT_PAGE}`);
});
