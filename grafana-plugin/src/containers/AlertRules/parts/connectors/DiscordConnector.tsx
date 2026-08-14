import React, { useCallback } from 'react';

import { cx } from '@emotion/css';
import { InlineSwitch, Stack, useStyles2 } from '@grafana/ui';
import { UserActions } from 'helpers/authorization/authorization';
import { StackSize } from 'helpers/consts';
import { observer } from 'mobx-react';

import { GSelect } from 'containers/GSelect/GSelect';
import { WithPermissionControlTooltip } from 'containers/WithPermissionControl/WithPermissionControlTooltip';
import { ChannelFilter } from 'models/channel_filter/channel_filter.types';
import { DiscordChannel } from 'models/discord/discord.types';
import { useStore } from 'state/useStore';

import { getConnectorsStyles } from './Connectors.styles';

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
      </Stack>
    </div>
  );
});
