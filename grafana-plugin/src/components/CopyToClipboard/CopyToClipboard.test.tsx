import { vi } from 'vitest';

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { openErrorNotification } from 'helpers/helpers';
import { CopyToClipboard, copyText } from './CopyToClipboard';

vi.mock('helpers/helpers', () => ({ openErrorNotification: vi.fn() }));
const setClipboard = (value: unknown) => Object.defineProperty(navigator, 'clipboard', { configurable: true, value });
afterEach(() => {
  setClipboard(undefined);
  vi.clearAllMocks();
});

it('reports success only after the clipboard write and preserves the child click handler', async () => {
  let resolve: () => void;
  const writeText = vi.fn(
    () =>
      new Promise<void>((done) => {
        resolve = done;
      })
  );
  setClipboard({ writeText });
  const onCopy = vi.fn();
  const onClick = vi.fn();
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
  setClipboard({ writeText: vi.fn().mockRejectedValue(new Error('Denied')) });
  document.execCommand = vi.fn(() => false);
  const onCopy = vi.fn();
  render(
    <CopyToClipboard text="token" onCopy={onCopy}>
      <button>Copy</button>
    </CopyToClipboard>
  );
  fireEvent.click(screen.getByText('Copy'));
  await waitFor(() => expect(openErrorNotification).toHaveBeenCalledTimes(1));
  expect(onCopy).not.toHaveBeenCalled();
});

it('copies inside a modal on HTTP and restores focus without leaving the secret in the DOM', async () => {
  setClipboard(undefined);
  render(
    <div role="dialog">
      <button>Original</button>
    </div>
  );
  const button = screen.getByText('Original');
  button.focus();
  document.execCommand = vi.fn(() => {
    expect(screen.getByRole('dialog').contains(document.querySelector('textarea'))).toBe(true);
    return true;
  });
  await copyText('secret');
  expect(document.execCommand).toHaveBeenCalledWith('copy');
  expect(document.activeElement).toBe(button);
  expect(document.querySelector('textarea')).toBeNull();
  document.execCommand = vi.fn(() => false);
  await expect(copyText('secret')).rejects.toThrow();
  expect(document.querySelector('textarea')).toBeNull();
});

it('uses the browser fallback when the Clipboard API is exposed but rejects writes', async () => {
  setClipboard({ writeText: vi.fn().mockRejectedValue(new Error('Document is not focused')) });
  document.execCommand = vi.fn(() => true);
  await expect(copyText('secret')).resolves.toBeUndefined();
  expect(document.execCommand).toHaveBeenCalledWith('copy');
  expect(document.querySelector('textarea')).toBeNull();
});
