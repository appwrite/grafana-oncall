import React, { ReactElement, useEffect, useState } from 'react';

import { SelectableValue } from '@grafana/data';
import { usePluginLinks } from '@grafana/runtime';
import { Button, Dropdown, Modal, Select, Stack, ToolbarButton } from '@grafana/ui';
import { OnCallPluginExtensionPoints } from 'app-types';
import { StackSize } from 'helpers/consts';
import { observer } from 'mobx-react';

import { ActionKey } from 'models/loader/action-keys';
import { ApiSchemas } from 'network/oncall-api/api.types';
import { useStore } from 'state/useStore';

import { ExtensionLinkMenu } from './ExtensionLinkMenu';

interface Props {
  alertGroup: ApiSchemas['AlertGroup'];
  extensionPointId: OnCallPluginExtensionPoints;
  declareIncidentLink?: string;
  grafanaIncidentId: string | null;
}

export function ExtensionLinkDropdown({
  alertGroup,
  extensionPointId,
  declareIncidentLink,
  grafanaIncidentId,
}: Props): ReactElement | null {
  const [isOpen, setIsOpen] = useState(false);
  const [isTriggerWebhookModalOpen, setIsTriggerWebhookModalOpen] = useState(false);
  const context = useExtensionPointContext(alertGroup);
  const { links, isLoading } = usePluginLinks({ context, extensionPointId, limitPerPlugin: 3 });

  if (isLoading) {
    return null;
  }

  const onOpenTriggerWebhookModal = async () => {
    setIsOpen(false);
    setIsTriggerWebhookModalOpen(true);
  };

  const menu = (
    <ExtensionLinkMenu
      extensions={links}
      webhookModal={{
        onOpenModal: onOpenTriggerWebhookModal,
      }}
      declareIncidentLink={declareIncidentLink}
      grafanaIncidentId={grafanaIncidentId}
    />
  );

  return (
    <div>
      <TriggerManualWebhookModal
        alertGroup={alertGroup}
        isModalOpen={isTriggerWebhookModalOpen}
        setIsModalOpen={setIsTriggerWebhookModalOpen}
      />

      <Dropdown onVisibleChange={setIsOpen} placement="bottom-start" overlay={menu}>
        <ToolbarButton aria-label="Actions" variant="canvas" isOpen={isOpen}>
          Actions
        </ToolbarButton>
      </Dropdown>
    </div>
  );
}

interface TriggerManualWebhookModalProps {
  alertGroup: ApiSchemas['AlertGroup'];
  isModalOpen: boolean;
  setIsModalOpen: (isOpen: boolean) => void;
}

const TriggerManualWebhookModal = observer(
  ({ isModalOpen, setIsModalOpen, alertGroup }: TriggerManualWebhookModalProps) => {
    const store = useStore();
    const [selectedWebhookOption, setSelectedWebhookOption] = useState<SelectableValue<string>>(null);

    useEffect(() => {
      (async () => {
        if (isModalOpen) {
          await store.outgoingWebhookStore.updateItems(
            {
              trigger_type: 0,
              integration: alertGroup.alert_receive_channel.id,
            },
            true
          );
        }
      })();
    }, [isModalOpen]);

    return (
      <Modal isOpen={isModalOpen} title={'Select outgoing webhook to trigger'} onDismiss={() => setIsModalOpen(false)}>
        <Stack direction="column" gap={StackSize.lg}>
          <Select
            isLoading={store.loaderStore.isLoading(ActionKey.FETCH_WEBHOOKS)}
            menuShouldPortal
            value={selectedWebhookOption}
            onChange={(option) => setSelectedWebhookOption(option)}
            options={Object.values(store.outgoingWebhookStore.items).map((item) => ({
              label: item.name,
              value: item.id,
            }))}
          />

          <Stack gap={StackSize.md} justifyContent={'flex-end'}>
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={onTriggerWebhook}
              disabled={selectedWebhookOption === null || store.loaderStore.isLoading(ActionKey.TRIGGER_MANUAL_WEBHOOK)}
            >
              Trigger webhook
            </Button>
          </Stack>
        </Stack>
      </Modal>
    );

    async function onTriggerWebhook() {
      await store.outgoingWebhookStore.triggerManualWebhook(selectedWebhookOption.value, alertGroup.pk);
      setIsModalOpen(false);
      setSelectedWebhookOption(null);
    }
  }
);

function useExtensionPointContext(incident: ApiSchemas['AlertGroup']): PluginExtensionOnCallAlertGroupContext {
  return { alertGroup: incident };
}

// This is the 'context' that will be passed to plugin extensions when they
// are created (in `getPluginLinkExtensions`, provided by Grafana).
//
// Other plugins should be able to use this context type in the `configure`
// or `onClick` handler of their extension.
interface PluginExtensionOnCallAlertGroupContext {
  alertGroup: ApiSchemas['AlertGroup'];
}
