import React, { cloneElement, ReactElement } from 'react';

import { openErrorNotification } from 'helpers/helpers';

export async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Embedded/managed browsers can expose the API while disallowing writes.
    }
  }

  // Older browsers and remote HTTP installations do not expose the Clipboard API.
  const focused = document.activeElement as HTMLElement;
  const selection = document.getSelection();
  const ranges = Array.from({ length: selection?.rangeCount ?? 0 }, (_, i) => selection.getRangeAt(i));
  const input = document.createElement('textarea');
  input.value = text;
  input.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
  document.body.appendChild(input);
  try {
    input.select();
    if (!document.execCommand('copy')) {
      throw new Error('Clipboard unavailable');
    }
  } finally {
    input.remove();
    focused?.focus();
    selection?.removeAllRanges();
    ranges.forEach((range) => selection?.addRange(range));
  }
}

export function CopyToClipboard({
  text,
  onCopy,
  children,
}: {
  text: string;
  onCopy?: () => void;
  children: ReactElement;
}) {
  return cloneElement(children, {
    onClick: async (event: React.MouseEvent) => {
      children.props.onClick?.(event);
      try {
        await copyText(text);
        onCopy?.();
      } catch {
        openErrorNotification('Unable to copy. Select and copy the text manually.');
      }
    },
  });
}
