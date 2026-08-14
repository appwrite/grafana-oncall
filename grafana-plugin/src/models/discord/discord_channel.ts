import { action, observable, makeObservable, runInAction } from 'mobx';

import { BaseStore } from 'models/base_store';
import { makeRequest } from 'network/network';
import { RootStore } from 'state/rootStore';

import { DiscordChannel } from './discord.types';

export class DiscordChannelStore extends BaseStore {
  @observable.shallow
  items: { [id: string]: DiscordChannel } = {};

  @observable.shallow
  searchResult: { [key: string]: Array<DiscordChannel['id']> } = {};

  constructor(rootStore: RootStore) {
    super(rootStore);

    makeObservable(this);

    this.path = '/discord/channels/';
  }

  @action.bound
  async updateById(id: DiscordChannel['id']) {
    const response = await this.getById(id);

    runInAction(() => {
      this.items = {
        ...this.items,
        [id]: response,
      };
    });
  }

  @action.bound
  async updateItems(query = '') {
    const result = await this.getAll();

    runInAction(() => {
      this.items = {
        ...this.items,
        ...result.reduce(
          (acc: { [key: string]: DiscordChannel }, item: DiscordChannel) => ({
            ...acc,
            [item.id]: item,
          }),
          {}
        ),
      };

      this.searchResult = {
        ...this.searchResult,
        [query]: result.map((item: DiscordChannel) => item.id),
      };
    });
  }

  getSearchResult = (query = '') => {
    if (!this.searchResult[query]) {
      return undefined;
    }
    return this.searchResult[query].map((discordChannelId: DiscordChannel['id']) => this.items[discordChannelId]);
  };

  @action.bound
  async makeDiscordChannelDefault(id: DiscordChannel['id']) {
    return makeRequest(`${this.path}${id}/set_default`, {
      method: 'POST',
    });
  }

  async deleteDiscordChannel(id: DiscordChannel['id']) {
    return super.delete(id);
  }
}
