import React, { useCallback, useState } from 'react';

import { css } from '@emotion/css';
import { Button, Modal, Field, Input, Stack, useStyles2 } from '@grafana/ui';
import { UserActions } from 'helpers/authorization/authorization';
import { openErrorNotification } from 'helpers/helpers';
import { get } from 'lodash-es';
import { observer } from 'mobx-react';
import { Controller, FormProvider, useForm } from 'react-hook-form';

import { WithPermissionControlTooltip } from 'containers/WithPermissionControl/WithPermissionControlTooltip';
import { useStore } from 'state/useStore';

interface DiscordIntegrationProps {
  disabled?: boolean;
  size?: 'md' | 'lg';
  onUpdate: () => void;
}

export const DiscordIntegrationButton = observer((props: DiscordIntegrationProps) => {
  const { disabled, size = 'md', onUpdate } = props;

  const [showModal, setShowModal] = useState<boolean>(false);

  const onModalCreateCallback = useCallback(() => {
    setShowModal(true);
  }, []);

  const onModalCancelCallback = useCallback(() => {
    setShowModal(false);
  }, []);

  const onModalUpdateCallback = useCallback(() => {
    setShowModal(false);

    onUpdate();
  }, [onUpdate]);

  return (
    <>
      <WithPermissionControlTooltip userAction={UserActions.IntegrationsWrite}>
        <Button size={size} variant="primary" icon="plus" disabled={disabled} onClick={onModalCreateCallback}>
          Add Discord channel
        </Button>
      </WithPermissionControlTooltip>
      {showModal && <DiscordChannelForm onHide={onModalCancelCallback} onUpdate={onModalUpdateCallback} />}
    </>
  );
});

interface DiscordCreationModalProps {
  onHide: () => void;
  onUpdate: () => void;
}

interface FormFields {
  channelId: string;
}

const DiscordChannelForm = (props: DiscordCreationModalProps) => {
  const { onHide, onUpdate } = props;
  const store = useStore();

  const formMethods = useForm<FormFields>({
    mode: 'onChange',
  });

  const {
    control,
    watch,
    formState: { errors },
    handleSubmit,
  } = formMethods;

  const channelId = watch('channelId');

  const styles = useStyles2(getStyles);

  return (
    <Modal title="Add Discord Channel" isOpen closeOnEscape={false} onDismiss={onUpdate}>
      <FormProvider {...formMethods}>
        <form onSubmit={handleSubmit(onCreateChannelCallback)}>
          <Stack direction="column">
            {renderChannelIdInput()}
            <Stack justifyContent="flex-end">
              <Button variant="secondary" onClick={() => onHide()}>
                Cancel
              </Button>
              <Button type="submit" disabled={!channelId} variant="primary">
                Create
              </Button>
            </Stack>
          </Stack>
        </form>
      </FormProvider>
    </Modal>
  );

  function renderChannelIdInput() {
    return (
      <Controller
        name="channelId"
        control={control}
        rules={{ required: 'Channel Id is required' }}
        render={({ field }) => (
          <Field
            label="Discord Channel ID"
            description="Turn on Developer Mode in Discord, then right-click the channel and choose Copy Channel ID."
            invalid={Boolean(errors['channelId'])}
            error={errors['channelId']?.message}
            className={styles.field}
          >
            <Input
              {...field}
              className={styles.channelFormFieldInput}
              maxLength={50}
              placeholder="Enter Discord Channel ID"
              autoFocus
            />
          </Field>
        )}
      />
    );
  }

  async function onCreateChannelCallback() {
    try {
      await store.discordChannelStore.create({ channel_id: channelId }, true);
      onUpdate();
    } catch (error) {
      openErrorNotification(get(error, 'response.data.detail', 'error creating channel'));
    }
  }
};

const getStyles = () => {
  return {
    channelFormFieldInput: css`
      border-top-right-radius: 0;
      border-bottom-right-radius: 0;
    `,

    field: css`
      flex-grow: 1;
    `,
  };
};
