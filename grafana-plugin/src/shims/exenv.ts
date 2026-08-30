export const canUseDOM = Boolean(typeof window !== 'undefined' && window.document && window.document.createElement);

export const canUseWorkers = typeof Worker !== 'undefined';
export const canUseEventListeners = canUseDOM && Boolean(window.addEventListener || 'attachEvent' in window);
export const canUseViewport = canUseDOM && Boolean(window.screen);

export default {
  canUseDOM,
  canUseWorkers,
  canUseEventListeners,
  canUseViewport,
};
