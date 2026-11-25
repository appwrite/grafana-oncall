import { vi } from 'vitest';

import { act, renderHook } from '@testing-library/react';
import { useMediaQuery } from './useMediaQuery';

it('updates at a breakpoint and unsubscribes when the query changes or unmounts', () => {
  const media = new EventTarget() as EventTarget & { matches: boolean };
  media.matches = false;
  const remove = vi.spyOn(media, 'removeEventListener');
  window.matchMedia = vi.fn().mockReturnValue(media);
  const { result, rerender, unmount } = renderHook(({ query }) => useMediaQuery({ query }), {
    initialProps: { query: '(min-width: 600px)' },
  });
  expect(result.current).toBe(false);
  act(() => {
    media.matches = true;
    media.dispatchEvent(new Event('change'));
  });
  expect(result.current).toBe(true);
  rerender({ query: '(min-width: 800px)' });
  expect(window.matchMedia).toHaveBeenLastCalledWith('(min-width: 800px)');
  unmount();
  expect(remove).toHaveBeenCalledWith('change', expect.any(Function));
});
