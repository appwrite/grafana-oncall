import type { ComponentClass } from 'react';

import { AppPlugin, PluginExtensionPoints } from '@grafana/data';
import { getIsIrmPluginPresent, IRM_TAB } from 'helpers/consts';
import { isCurrentGrafanaVersionEqualOrGreaterThan } from 'helpers/helpers';

import { MobileAppConnectionWrapper } from 'containers/MobileAppConnection/MobileAppConnection';
import { PluginConfigPage } from 'containers/PluginConfigPage/PluginConfigPage';
import { GrafanaPluginRootPage } from 'plugin/GrafanaPluginRootPage';

import { OnCallPluginConfigPageProps, OnCallPluginMetaJSONData } from './app-types';

const plugin = new AppPlugin<OnCallPluginMetaJSONData>().setRootPage(GrafanaPluginRootPage).addConfigPage({
  title: 'Configuration',
  icon: 'cog',
  body: PluginConfigPage as unknown as ComponentClass<OnCallPluginConfigPageProps, unknown>,
  id: 'configuration',
});

if (isUseProfileExtensionPointEnabled()) {
  const extensionPointId = PluginExtensionPoints.UserProfileTab;

  plugin.addComponent({
    title: IRM_TAB,
    description: 'IRM settings',
    component: MobileAppConnectionWrapper,
    targets: [extensionPointId],
  });
}

function isUseProfileExtensionPointEnabled(): boolean {
  return (
    isCurrentGrafanaVersionEqualOrGreaterThan({ minMajor: 10, minMinor: 3 }) &&
    PluginExtensionPoints != null &&
    'UserProfileTab' in PluginExtensionPoints &&
    !getIsIrmPluginPresent() &&
    !!plugin.addComponent
  );
}

export { plugin };
