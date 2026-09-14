import React, { PropsWithChildren, useCallback, useSyncExternalStore } from 'react';

import { locationService } from '@grafana/runtime';
import { NavigationType, Router } from 'react-router-v7';

// Bundle the patched router under an alias because Grafana supplies its own
// react-router external. Share Grafana's history so both routers stay in sync.
export function PluginRouter({ children }: PropsWithChildren) {
  const history = locationService.getHistory();
  const subscribe = useCallback((notify: () => void) => history.listen(notify), [history]);
  const getSnapshot = useCallback(() => history.location, [history]);
  const location = useSyncExternalStore(subscribe, getSnapshot);

  return (
    <Router location={location} navigationType={history.action as NavigationType} navigator={history}>
      {children}
    </Router>
  );
}
