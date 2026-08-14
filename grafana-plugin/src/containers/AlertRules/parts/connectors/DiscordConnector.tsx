import React, { useCallback } from 'react';

import { cx } from '@emotion/css';
import { SelectableValue } from '@grafana/data';
import { InlineSwitch, Input, Select, Stack, useStyles2 } from '@grafana/ui';
import { UserActions } from 'helpers/authorization/authorization';
import { StackSize } from 'helpers/consts';
import { observer } from 'mobx-react';

import { GSelect } from 'containers/GSelect/GSelect';
import { WithPermissionControlTooltip } from 'containers/WithPermissionControl/WithPermissionControlTooltip';
import { ChannelFilter } from 'models/channel_filter/channel_filter.types';
import { DiscordChannel } from 'models/discord/discord.types';
import { useStore } from 'state/useStore';

import { getConnectorsStyles } from './Connectors.styles';

const SEVERITY_OPTIONS = [
  { value: 'alert', label: '🚨 Alert' },
  { value: 'warning', label: '⚠️ Warning' },
];

interface DiscordConnectorProps {
  channelFilterId: ChannelFilter['id'];
}

export const DiscordConnector = observer((props: DiscordConnectorProps) => {
  const { channelFilterId } = props;

  const store = useStore();
  const styles = useStyles2(getConnectorsStyles);

  const {
    alertReceiveChannelStore,
    discordChannelStore,
    // dereferencing items is needed to rerender GSelect
    discordChannelStore: { items: discordChannelItems },
  } = store;

  const channelFilter = alertReceiveChannelStore.channelFilters[channelFilterId];

  const handleDiscordChannelChange = useCallback((_value: DiscordChannel['id'], discordChannel: DiscordChannel) => {
    alertReceiveChannelStore.saveChannelFilter(channelFilterId, {
      notification_backends: {
        DISCORD: { channel: discordChannel?.id || null },
      },
    });
  }, []);

  const handleChannelFilterNotifyInDiscordChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    alertReceiveChannelStore.saveChannelFilter(channelFilterId, {
      notification_backends: { DISCORD: { enabled: event.target.checked } },
    });
  }, []);

  // How loud a still-open alert group from this route reads in Discord: an alert is red, a warning amber. Which
  // payloads count as either is what the route itself already decides.
  const handleSeverityChange = useCallback((option: SelectableValue<string>) => {
    alertReceiveChannelStore.saveChannelFilter(channelFilterId, {
      notification_backends: { DISCORD: { severity: option?.value || 'alert' } },
    });
  }, []);

  // The role OnCall pings when an escalation reaches "notify whole channel" or "notify group" — the step that means
  // nobody has picked the alert up.
  const handleEscalationRoleChange = useCallback((event: React.FocusEvent<HTMLInputElement>) => {
    alertReceiveChannelStore.saveChannelFilter(channelFilterId, {
      notification_backends: { DISCORD: { role: event.target.value.trim() } },
    });
  }, []);

  return (
    <div className={styles.root}>
      <Stack wrap="wrap" gap={StackSize.sm}>
        <div>
          <WithPermissionControlTooltip userAction={UserActions.IntegrationsWrite}>
            <InlineSwitch
              value={channelFilter.notification_backends?.DISCORD?.enabled}
              onChange={handleChannelFilterNotifyInDiscordChange}
              transparent
            />
          </WithPermissionControlTooltip>
        </div>
        Post to Discord channel
        <WithPermissionControlTooltip userAction={UserActions.IntegrationsWrite}>
          <GSelect<DiscordChannel>
            allowClear
            className={cx('select', 'control')}
            items={discordChannelItems}
            fetchItemsFn={discordChannelStore.updateItems}
            fetchItemFn={discordChannelStore.updateById}
            getSearchResult={discordChannelStore.getSearchResult}
            displayField="channel_name"
            valueField="id"
            placeholder="Select Discord Channel"
            value={channelFilter.notification_backends?.DISCORD?.channel}
            onChange={handleDiscordChannelChange}
          />
        </WithPermissionControlTooltip>
        as
        <WithPermissionControlTooltip userAction={UserActions.IntegrationsWrite}>
          <Select
            className={cx('select', 'control')}
            options={SEVERITY_OPTIONS}
            value={channelFilter.notification_backends?.DISCORD?.severity || 'alert'}
            onChange={handleSeverityChange}
            aria-label="Discord severity"
          />
        </WithPermissionControlTooltip>
        escalating to role
        <WithPermissionControlTooltip userAction={UserActions.IntegrationsWrite}>
          <Input
            className={cx('control')}
            defaultValue={channelFilter.notification_backends?.DISCORD?.role || ''}
            onBlur={handleEscalationRoleChange}
            placeholder="Role ID (optional)"
            aria-label="Discord escalation role"
          />
        </WithPermissionControlTooltip>
      </Stack>
    </div>
  );
});
