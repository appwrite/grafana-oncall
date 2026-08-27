import React, { Component } from 'react';

import { css } from '@emotion/css';
import { Badge, Button, LoadingPlaceholder, Stack } from '@grafana/ui';
import { DOCS_DISCORD_SETUP, StackSize } from 'helpers/consts';
import { observer } from 'mobx-react';

import { Block } from 'components/GBlock/Block';
import { GTable } from 'components/GTable/GTable';
import { PluginLink } from 'components/PluginLink/PluginLink';
import { Text } from 'components/Text/Text';
import { WithConfirm } from 'components/WithConfirm/WithConfirm';
import { DiscordIntegrationButton } from 'containers/DiscordIntegrationButton/DiscordIntegrationButton';
import { DiscordChannel } from 'models/discord/discord.types';
import { AppFeature } from 'state/features';
import { WithStoreProps } from 'state/types';
import { withMobXProviderContext } from 'state/withStore';

interface DiscordProps extends WithStoreProps {}

interface DiscordState {}

@observer
class _DiscordSettings extends Component<DiscordProps, DiscordState> {
  state: DiscordState = {};

  componentDidMount() {
    this.update();
  }

  update = () => {
    this.props.store.discordChannelStore.updateItems();
  };

  render() {
    const { store } = this.props;
    const { discordChannelStore, organizationStore } = store;
    const connectedChannels = discordChannelStore.getSearchResult();
    const styles = getStyles();

    const discordConfigured = organizationStore.currentOrganization?.env_status.discord_configured;

    if (!discordConfigured && store.hasFeature(AppFeature.LiveSettings)) {
      return (
        <Stack direction="column" gap={StackSize.lg}>
          <Text.Title level={2}>Connect Discord server</Text.Title>
          {this.renderInfoBlock()}
          <PluginLink query={{ page: 'live-settings' }}>
            <Button variant="primary">Setup ENV Variables</Button>
          </PluginLink>
        </Stack>
      );
    }

    if (!connectedChannels) {
      return <LoadingPlaceholder text="Loading..." />;
    }

    if (!connectedChannels.length) {
      return (
        <Stack direction="column" gap={StackSize.lg}>
          <Text.Title level={2}>Connect Discord server</Text.Title>
          {this.renderInfoBlock()}
          <Stack>
            <DiscordIntegrationButton size="md" onUpdate={this.update} />
            {store.hasFeature(AppFeature.LiveSettings) && (
              <PluginLink query={{ page: 'live-settings' }}>
                <Button variant="primary">See ENV Variables</Button>
              </PluginLink>
            )}
          </Stack>
        </Stack>
      );
    }

    const columns = [
      {
        width: '35%',
        title: 'Channel Name',
        key: 'name',
        render: this.renderChannelName,
      },
      {
        width: '35%',
        title: 'Channel ID',
        render: this.renderChannelId,
      },
      {
        width: '30%',
        key: 'action',
        render: this.renderActionButtons,
      },
    ];

    return (
      <div className={styles.root}>
        <GTable
          title={() => (
            <div className={styles.header}>
              <Text.Title level={3}>Discord Channels</Text.Title>
              <DiscordIntegrationButton onUpdate={this.update} />
            </div>
          )}
          emptyText="No Discord channels connected"
          rowKey="id"
          columns={columns}
          data={connectedChannels}
        />
      </div>
    );
  }

  renderInfoBlock = () => {
    const styles = getStyles();

    return (
      <Block bordered withBackground className={styles.discordInfoBlock}>
        <Stack direction="column" alignItems="center">
          <Text className={styles.infoBlockText}>
            Connecting a Discord channel will post alert groups there, with buttons to acknowledge and resolve them.
          </Text>
          <Text className={styles.infoBlockText}>
            After connecting a channel, your team members need to link their personal Discord accounts before those
            buttons can act on their behalf.
          </Text>
          <Text type="secondary" className={styles.infoBlockText}>
            More details in{' '}
            <a href={DOCS_DISCORD_SETUP} target="_blank" rel="noreferrer">
              <Text type="link">our documentation</Text>
            </a>
          </Text>
        </Stack>
      </Block>
    );
  };

  renderChannelName = (record: DiscordChannel) => (
    <>
      {record.channel_name} {record.is_default_channel && <Badge text="Default" color="green" />}
    </>
  );

  renderChannelId = (record: DiscordChannel) => <>{record.channel_id}</>;

  renderActionButtons = (record: DiscordChannel) => (
    <Stack justifyContent="flex-end">
      <Button
        onClick={() => this.makeDiscordChannelDefault(record.id)}
        disabled={record.is_default_channel}
        fill="text"
      >
        Make default
      </Button>
      <WithConfirm title="Are you sure to disconnect?">
        <Button onClick={() => this.disconnectDiscordChannel(record.id)} fill="text" variant="destructive">
          Disconnect
        </Button>
      </WithConfirm>
    </Stack>
  );

  makeDiscordChannelDefault = async (id: DiscordChannel['id']) => {
    const { discordChannelStore } = this.props.store;

    await discordChannelStore.makeDiscordChannelDefault(id);
    discordChannelStore.updateItems();
  };

  disconnectDiscordChannel = async (id: DiscordChannel['id']) => {
    const { discordChannelStore } = this.props.store;

    await discordChannelStore.deleteDiscordChannel(id);
    discordChannelStore.updateItems();
  };
}

export const DiscordSettings = withMobXProviderContext(_DiscordSettings);

const getStyles = () => {
  return {
    root: css`
      display: block;
    `,
    header: css`
      display: flex;
      justify-content: space-between;
    `,
    discordInfoBlock: css`
      text-align: center;
      width: 725px;
    `,
    infoBlockText: css`
      margin-left: 48px;
      margin-right: 48px;
      margin-top: 24px;
    `,
  };
};
