import React, { useEffect, useState } from 'react';

import { css } from '@emotion/css';
import { Field, Icon, Input, Stack, useStyles2 } from '@grafana/ui';
import { UserActions } from 'helpers/authorization/authorization';
import { DOCS_DISCORD_SETUP, StackSize } from 'helpers/consts';
import { openNotification } from 'helpers/helpers';
import { observer } from 'mobx-react';
import CopyToClipboard from 'react-copy-to-clipboard';

import { Text } from 'components/Text/Text';
import { WithPermissionControlDisplay } from 'containers/WithPermissionControl/WithPermissionControlDisplay';
import { UserHelper } from 'models/user/user.helpers';
import { useStore } from 'state/useStore';

export const DiscordInfo = observer(() => {
  const { userStore } = useStore();
  const [verificationCode, setVerificationCode] = useState<string>();

  const styles = useStyles2(getStyles);

  useEffect(() => {
    (async () => {
      setVerificationCode(await UserHelper.fetchBackendConfirmationCode(userStore.currentUserPk, 'DISCORD'));
    })();
  }, []);

  // The code expires quickly, so reloading the user on the way out is what makes the connector show as linked.
  useEffect(() => {
    return () => {
      userStore.loadCurrentUser();
    };
  }, []);

  return (
    <WithPermissionControlDisplay userAction={UserActions.UserSettingsWrite}>
      <Stack direction="column" gap={StackSize.md}>
        <Text.Title level={2}>Connect Discord account</Text.Title>

        <Text type="secondary">
          Linking your Discord account lets the Acknowledge and Resolve buttons on an alert group act as you, and lets
          a notification policy reach you in Discord.
        </Text>

        <Text type="secondary">1. Copy this verification code, which is valid for ten minutes:</Text>
        <Field className={styles.field}>
          <Input
            id="discordVerificationCode"
            value={verificationCode}
            suffix={
              <CopyToClipboard text={verificationCode} onCopy={() => openNotification('Code is copied')}>
                <Icon name="copy" />
              </CopyToClipboard>
            }
          />
        </Field>

        <Text type="secondary">
          2. In Discord, run <Text className={styles.command}>/oncall-link</Text> and paste it as the{' '}
          <Text className={styles.command}>code</Text> option. Only you will see the reply.
        </Text>

        <Text type="secondary">3. Refresh this page.</Text>

        <Text type="secondary">
          More details in{' '}
          <a href={DOCS_DISCORD_SETUP} target="_blank" rel="noreferrer">
            <Text type="link">our documentation</Text>
          </a>
        </Text>
      </Stack>
    </WithPermissionControlDisplay>
  );
});

const getStyles = () => {
  return {
    field: css`
      width: 100%;
      margin-bottom: 0;
    `,
    command: css`
      font-family: monospace;
    `,
  };
};
