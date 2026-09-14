import React from 'react';

import { locationService } from '@grafana/runtime';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { Link, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-v7';

import { PluginRouter } from './PluginRouter';

jest.mock('@grafana/runtime', () => {
  const { HistoryWrapper } = jest.requireActual('@grafana/runtime');
  return { locationService: new HistoryWrapper() };
});

const root = '/a/grafana-oncall-app';

function Page() {
  const location = useLocation();
  const params = useParams();
  const navigate = useNavigate();
  return (
    <>
      <output data-testid="location">{location.pathname + location.search + location.hash}</output>
      <output data-testid="id">{params.id}</output>
      <Link to={`${root}/integrations/42?tab=outgoing#details`}>Integration</Link>
      <button onClick={() => navigate(`${root}/users`, { replace: true })}>Replace</button>
      <button onClick={() => navigate(-1)}>Back</button>
    </>
  );
}

function renderPlugin() {
  return render(
    <PluginRouter>
      <Routes>
        <Route
          path={`${root}/*`}
          element={
            <Routes>
              <Route path="integrations/:id" element={<Page />} />
              <Route path="*" element={<Page />} />
            </Routes>
          }
        />
      </Routes>
    </PluginRouter>
  );
}

beforeEach(() => locationService.replace(`${root}/alert-groups`));

test('plugin links preserve absolute URLs, parameters, query strings and hashes in Grafana history', () => {
  renderPlugin();
  expect(screen.getByRole('link')).toHaveAttribute('href', `${root}/integrations/42?tab=outgoing#details`);
  fireEvent.click(screen.getByText('Integration'));
  expect(locationService.getLocation().pathname).toBe(`${root}/integrations/42`);
  expect(screen.getByTestId('id')).toHaveTextContent('42');
  expect(screen.getByTestId('location')).toHaveTextContent(`${root}/integrations/42?tab=outgoing#details`);
});

test('Grafana navigation, replace and back update the plugin router', () => {
  renderPlugin();
  act(() => locationService.push(`${root}/integrations/7`));
  expect(screen.getByTestId('id')).toHaveTextContent('7');
  fireEvent.click(screen.getByText('Replace'));
  expect(locationService.getHistory().action).toBe('REPLACE');
  expect(screen.getByTestId('location')).toHaveTextContent(`${root}/users`);
  fireEvent.click(screen.getByText('Back'));
  expect(screen.getByTestId('location')).toHaveTextContent(`${root}/alert-groups`);
  act(() => locationService.getHistory().goForward());
  expect(screen.getByTestId('location')).toHaveTextContent(`${root}/users`);
});

test('unmount removes the Grafana history listener', () => {
  const unsubscribe = jest.fn();
  const listen = jest.spyOn(locationService.getHistory(), 'listen').mockReturnValue(unsubscribe);
  const { unmount } = renderPlugin();
  unmount();
  expect(unsubscribe).toHaveBeenCalledTimes(1);
  listen.mockRestore();
});
