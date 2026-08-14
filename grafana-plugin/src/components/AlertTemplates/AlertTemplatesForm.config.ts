import { merge } from 'lodash-es'

import { AppFeature } from 'state/features';

import { TemplateForEdit, commonTemplateForEdit } from './CommonAlertTemplatesForm.config';

export const getTemplatesForEdit = (features: Record<string, boolean>) => {
  const templatesForEdit = {...commonTemplateForEdit}
  if (features?.[AppFeature.MsTeams]) {
    merge(templatesForEdit, msteamsTemplateForEdit)
  }
  if (features?.[AppFeature.Mattermost]) {
    merge(templatesForEdit, mattermostTemplateForEdit)
  }
  if (features?.[AppFeature.Discord]) {
    merge(templatesForEdit, discordTemplateForEdit)
  }
  return templatesForEdit;
};

const msteamsTemplateForEdit: { [id: string]: TemplateForEdit } = {
  msteams_title_template: {
    name: 'msteams_title_template',
    displayName: 'MS Teams title',
    description: '',
    additionalData: {
      chatOpsName: 'msteams',
      chatOpsDisplayName: 'MS Teams',
    },
    type: 'plain',
  },
  msteams_message_template: {
    name: 'msteams_message_template',
    displayName: 'MS Teams message',
    description: '',
    additionalData: {
      chatOpsName: 'msteams',
      chatOpsDisplayName: 'MS Teams',
    },
    type: 'plain',
  },
  msteams_image_url_template: {
    name: 'msteams_image_url_template',
    displayName: 'MS Teams image url',
    description: '',
    additionalData: {
      chatOpsName: 'msteams',
      chatOpsDisplayName: 'MS Teams',
    },
    type: 'plain',
  },
};

const mattermostTemplateForEdit: { [id: string]: TemplateForEdit } = {
  mattermost_title_template: {
    name: 'mattermost_title_template',
    displayName: 'Mattermost title',
    description: '',
    additionalData: {
      chatOpsName: 'mattermost',
      chatOpsDisplayName: 'Mattermost',
    },
    type: 'plain',
  },
  mattermost_message_template: {
    name: 'mattermost_message_template',
    displayName: 'Mattermost message',
    description: '',
    additionalData: {
      chatOpsName: 'mattermost',
      chatOpsDisplayName: 'Mattermost',
    },
    type: 'plain',
  },
  mattermost_image_url_template: {
    name: 'mattermost_image_url_template',
    displayName: 'Mattermost image url',
    description: '',
    additionalData: {
      chatOpsName: 'mattermost',
      chatOpsDisplayName: 'Mattermost',
    },
    type: 'plain',
  },
};

const discordTemplateForEdit: { [id: string]: TemplateForEdit } = {
  discord_title_template: {
    name: 'discord_title_template',
    displayName: 'Discord title',
    description: '',
    additionalData: {
      chatOpsName: 'discord',
      chatOpsDisplayName: 'Discord',
    },
    type: 'plain',
  },
  discord_message_template: {
    name: 'discord_message_template',
    displayName: 'Discord message',
    description: '',
    additionalData: {
      chatOpsName: 'discord',
      chatOpsDisplayName: 'Discord',
    },
    type: 'plain',
  },
  discord_image_url_template: {
    name: 'discord_image_url_template',
    displayName: 'Discord image url',
    description: '',
    additionalData: {
      chatOpsName: 'discord',
      chatOpsDisplayName: 'Discord',
    },
    type: 'plain',
  },
};

export const FORM_NAME = 'AlertTemplates';
