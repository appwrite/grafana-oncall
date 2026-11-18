import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { openErrorNotification } from 'helpers/helpers';
import { CopyToClipboard, copyText } from './CopyToClipboard';

jest.mock('helpers/helpers', () => ({ openErrorNotification: jest.fn() }));
const setClipboard = (value: unknown) => Object.defineProperty(navigator, 'clipboard', { configurable: true, value });
afterEach(() => {
  setClipboard(undefined);
  jest.clearAllMocks();
});

it('reports success only after the clipboard write and preserves the child click handler', async () => {
  let resolve: () => void;
  const writeText = jest.fn(
    () =>
      new Promise<void>((done) => {
        resolve = done;
      })
  );
  setClipboard({ writeText });
  const onCopy = jest.fn();
  const onClick = jest.fn();
  render(
    <CopyToClipboard text="token" onCopy={onCopy}>
      <button onClick={onClick}>Copy</button>
    </CopyToClipboard>
  );
  fireEvent.click(screen.getByText('Copy'));
  expect(onClick).toHaveBeenCalledTimes(1);
  expect(writeText).toHaveBeenCalledWith('token');
  expect(onCopy).not.toHaveBeenCalled();
  resolve();
  await waitFor(() => expect(onCopy).toHaveBeenCalledTimes(1));
});

it('reports permission errors without a false success notification', async () => {
  setClipboard({ writeText: jest.fn().mockRejectedValue(new Error('Denied')) });
  document.execCommand = jest.fn(() => false);
  const onCopy = jest.fn();
  render(
    <CopyToClipboard text="token" onCopy={onCopy}>
      <button>Copy</button>
    </CopyToClipboard>
  );
  fireEvent.click(screen.getByText('Copy'));
  await waitFor(() => expect(openErrorNotification).toHaveBeenCalledTimes(1));
  expect(onCopy).not.toHaveBeenCalled();
});

it('copies on HTTP deployments and restores focus without leaving the secret in the DOM', async () => {
  setClipboard(undefined);
  render(<button>Original</button>);
  const button = screen.getByText('Original');
  button.focus();
  document.execCommand = jest.fn(() => true);
  await copyText('secret');
  expect(document.execCommand).toHaveBeenCalledWith('copy');
  expect(document.activeElement).toBe(button);
  expect(document.querySelector('textarea')).toBeNull();
  document.execCommand = jest.fn(() => false);
  await expect(copyText('secret')).rejects.toThrow();
  expect(document.querySelector('textarea')).toBeNull();
});

it('uses the browser fallback when the Clipboard API is exposed but rejects writes', async () => {
  setClipboard({ writeText: jest.fn().mockRejectedValue(new Error('Document is not focused')) });
  document.execCommand = jest.fn(() => true);
  await expect(copyText('secret')).resolves.toBeUndefined();
  expect(document.execCommand).toHaveBeenCalledWith('copy');
  expect(document.querySelector('textarea')).toBeNull();
});
