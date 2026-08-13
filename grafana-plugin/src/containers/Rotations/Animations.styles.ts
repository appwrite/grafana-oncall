import { css, keyframes } from '@emotion/css';

const fadeIn = keyframes`
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
`;

export const getAnimationClasses = () => {
  return {
    /**
     * Fades children in as they are added. Applied to the container so that children the browser
     * has just inserted animate without every one of them needing to take a className.
     */
    fadeInChildren: css`
      & > * {
        animation: ${fadeIn} 500ms ease-in;
      }
    `,
  };
};
