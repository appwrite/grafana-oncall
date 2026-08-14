import React, { useCallback } from 'react';

import { Button, InlineField, Input, Stack } from '@grafana/ui';
import { StackSize } from 'helpers/consts';
import { observer } from 'mobx-react';

import { WithConfirm } from 'components/WithConfirm/WithConfirm';
import { UserSettingsTab } from 'containers/UserSettings/UserSettings.types';
import { ApiSchemas } from 'network/oncall-api/api.types';
import { useStore } from 'state/useStore';

interface DiscordConnectorProps {
  id: ApiSchemas['User']['pk'];
  onTabChange: (tab: UserSettingsTab) => void;
}

export const DiscordConnector = observer((props: DiscordConnectorProps) => {
  const { id, onTabChange } = props;

  const store = useStore();
  const { userStore } = store;

  const storeUser = userStore.items[id];

  const isCurrentUser = id === store.userStore.currentUserPk;

  const handleConnectButtonClick = useCallback(() => {
    onTabChange(UserSettingsTab.DiscordInfo);
  }, []);

  const handleUnlinkDiscordAccount = useCallback(() => {
    userStore.unlinkBackend(id, 'DISCORD');
  }, []);

  const discordConfigured = storeUser.messaging_backends['DISCORD'];

  return (
    <div>
      {discordConfigured ? (
        <InlineField label="Discord" labelWidth={12}>
          <Stack gap={StackSize.xs}>
            <Input disabled value={discordConfigured?.username ? '@' + discordConfigured?.username : ''} />
            <WithConfirm title="Are you sure to disconnect your Discord account?" confirmText="Disconnect">
              <Button
                disabled={!isCurrentUser}
                variant="destructive"
                icon="times"
                onClick={handleUnlinkDiscordAccount}
                tooltip="Unlink Discord Account"
              />
            </WithConfirm>
          </Stack>
        </InlineField>
      ) : (
        <div>
          <InlineField label="Discord" labelWidth={12} disabled={!isCurrentUser}>
            <Button onClick={handleConnectButtonClick}>Connect account</Button>
          </InlineField>
        </div>
      )}
    </div>
  );
});
