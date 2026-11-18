import React, { useEffect, useMemo } from 'react';

import { DEFAULT_PAGE, PLUGIN_ROOT } from 'helpers/consts';
import { getPathFromQueryParams } from 'helpers/url';
import { parseQuery } from 'helpers/query';
import { useNavigate } from 'react-router-v7';

export const NoMatch = () => {
  const navigate = useNavigate();

  const query = useMemo(() => parseQuery(window.location.search), [window.location.search]);

  useEffect(() => {
    if (query.page) {
      const path = getPathFromQueryParams(query);
      navigate(path);
    } else {
      navigate(`${PLUGIN_ROOT}/${DEFAULT_PAGE}`);
    }
  }, [query]);

  return <div>Not Found</div>;
};
