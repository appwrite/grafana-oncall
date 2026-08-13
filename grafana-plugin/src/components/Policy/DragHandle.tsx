import React from 'react';

import { cx } from '@emotion/css';
import { Icon, useStyles2 } from '@grafana/ui';
import { bem } from 'styles/utils.styles';

import { useSortableNode } from 'components/SortableList/SortableNode';

import { getPolicyStyles } from './Policy.styles';

export const DragHandle = ({ disabled }: { disabled?: boolean }) => {
  const styles = useStyles2(getPolicyStyles);
  const { handleProps } = useSortableNode();

  return (
    <div
      {...handleProps}
      className={cx(styles.control, styles.handle, { [bem(styles.handle, 'disabled')]: disabled })}
    >
      <Icon name="draggabledots" />
    </div>
  );
};
