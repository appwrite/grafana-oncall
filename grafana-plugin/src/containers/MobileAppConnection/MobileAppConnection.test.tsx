import { vi } from 'vitest';

import React from 'react';

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { UserHelper } from 'models/user/user.helpers';
import { ApiSchemas } from 'network/oncall-api/api.types';
import { rootStore } from 'state/rootStore';

import { MobileAppConnection } from './MobileAppConnection';

vi.mock('helpers/authorization/authorization', async (importOriginal) => ({
  ...(await importOriginal<typeof import('helpers/authorization/authorization')>()),
  isUserActionAllowed: vi.fn().mockReturnValue(true),
}));

const loadUserMock = vi.fn().mockReturnValue(undefined);

vi.mock('state/rootStore', () => ({
  rootStore: vi.fn(),
}));

const mockRootStore = (rest?: any, connected = false, cloud_connected = true) => {
  rootStore.userStore = {
    fetchItemById: loadUserMock,
    currentUser: {
      messaging_backends: {
        MOBILE_APP: { connected },
      },
    } as unknown as ApiSchemas['User'],
    ...(rest ? rest : {}),
  };

  rootStore.cloudStore = {
    getCloudConnectionStatus: vi.fn().mockReturnValue({ cloud_connection_status: cloud_connected }),
    cloudConnectionStatus: { cloud_connection_status: cloud_connected },
  } as any;

  // @ts-ignore
  rootStore.isOpenSource = vi.fn().mockReturnValue(true);
  rootStore.hasFeature = vi.fn().mockReturnValue(true);
};

const USER_PK = '8585';
const BACKEND = 'MOBILE_APP';

describe('MobileAppConnection', () => {
  test('', () => {
    expect(true).toBe(true);
  });
});

describe('MobileAppConnection', () => {
  beforeEach(() => {
    loadUserMock.mockClear();
    (rootStore as any).mockClear();
    mockRootStore();
    UserHelper.fetchBackendConfirmationCode = vi.fn().mockResolvedValueOnce('dfd');
  });

  test('it shows a loading message if it is currently fetching the QR code', async () => {
    render(<MobileAppConnection userPk={USER_PK} />);

    await waitFor(() => {
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledTimes(1);
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledWith(USER_PK, BACKEND);
    });
  });

  test('it shows an error message if there was an error fetching the QR code', async () => {
    UserHelper.fetchBackendConfirmationCode = vi.fn().mockRejectedValueOnce('dfd');
    render(<MobileAppConnection userPk={USER_PK} />);
    await screen.findByText(/.*error fetching your QR code.*/);

    await waitFor(() => {
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledTimes(1);
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledWith(USER_PK, BACKEND);
    });
  });

  test("it shows a QR code if the app isn't already connected", async () => {
    render(<MobileAppConnection userPk={USER_PK} />);

    await waitFor(() => {
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledTimes(1);
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledWith(USER_PK, BACKEND);
    });
  });

  test('if we disconnect the app, it disconnects and fetches a new QR code', async () => {
    mockRootStore(
      {
        unlinkBackend: vi.fn().mockResolvedValueOnce('asdfadsfafds'),
      },
      true
    );

    const component = render(<MobileAppConnection userPk={USER_PK} />);

    const button = await component.findByRole('button');

    // click the disconnect button, which opens the modal
    await userEvent.click(button);
    // click the confirm button within the modal, which actually triggers the callback
    await userEvent.click(screen.getByText('Remove'));

    await waitFor(() => {
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledTimes(1);
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledWith(USER_PK, BACKEND);

      expect(rootStore.userStore.unlinkBackend).toHaveBeenCalledTimes(1);
      expect(rootStore.userStore.unlinkBackend).toHaveBeenCalledWith(USER_PK, BACKEND);
    });
  });

  test('it shows a loading message if it is currently disconnecting', async () => {
    mockRootStore(
      {
        unlinkBackend: vi.fn().mockResolvedValueOnce(new Promise((resolve) => setTimeout(resolve, 500))),
      },
      true
    );

    render(<MobileAppConnection userPk={USER_PK} />);
    const button = await screen.findByRole('button');

    // click the disconnect button, which opens the modal
    await userEvent.click(button);
    // click the confirm button within the modal, which actually triggers the callback
    await userEvent.click(screen.getByText('Remove'));

    // wait for loading state
    await screen.findByText(/.*Loading.*/);

    await waitFor(() => {
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledTimes(1);
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledWith(USER_PK, BACKEND);

      expect(rootStore.userStore.unlinkBackend).toHaveBeenCalledTimes(1);
      expect(rootStore.userStore.unlinkBackend).toHaveBeenCalledWith(USER_PK, BACKEND);
    });
  });

  test('it shows an error message if there was an error disconnecting the mobile app', async () => {
    mockRootStore(
      {
        unlinkBackend: vi.fn().mockRejectedValueOnce('asdfadsfafds'),
      },
      true
    );

    render(<MobileAppConnection userPk={USER_PK} />);
    const button = await screen.findByTestId('test__disconnect');

    // click the disconnect button, which opens the modal
    await userEvent.click(button);
    // click the confirm button within the modal, which actually triggers the callback
    await userEvent.click(screen.getByText('Remove'));

    await screen.findByText(/.*error disconnecting your mobile app.*/);

    await waitFor(() => {
      expect(UserHelper.fetchBackendConfirmationCode).toHaveBeenCalledTimes(0);

      expect(rootStore.userStore.unlinkBackend).toHaveBeenCalledTimes(1);
      expect(rootStore.userStore.unlinkBackend).toHaveBeenCalledWith(USER_PK, BACKEND);
    });
  });

  test('it polls loadUser on first render if not connected', async () => {
    mockRootStore(
      {
        unlinkBackend: vi.fn().mockRejectedValueOnce('asdfadsfafds'),
      },
      false
    );

    render(<MobileAppConnection userPk={USER_PK} />);

    await waitFor(
      () => {
        expect(loadUserMock).toHaveBeenCalled();
      },
      { timeout: 6000 }
    );
  });

  test('it polls loadUser after disconnect', async () => {
    mockRootStore(
      {
        unlinkBackend: vi.fn().mockRejectedValueOnce('asdff'),
      },
      true
    );

    render(<MobileAppConnection userPk={USER_PK} />);
    const button = await screen.findByRole('button');

    loadUserMock.mockClear();

    await userEvent.click(button); // click the disconnect button, which opens the modal
    await userEvent.click(screen.getByText('Remove')); // click the confirm button within the modal, which actually triggers the callback

    await waitFor(
      () => {
        expect(loadUserMock).toHaveBeenCalled();
      },
      { timeout: 6000 }
    );
  });
});
