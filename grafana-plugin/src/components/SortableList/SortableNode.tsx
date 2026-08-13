import React, { createContext, useContext } from 'react';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface SortableNode {
  /** attach to the element that moves while dragging */
  setNodeRef?: (element: HTMLElement | null) => void;
  style?: React.CSSProperties;
  /** spread onto the element you grab to start a drag */
  handleProps?: Record<string, unknown>;
}

const SortableNodeContext = createContext<SortableNode>({});

/**
 * Lets an element deep inside a sortable item wire itself up as the drag target
 * (Timeline.Item) or the grab area (DragHandle), without threading props through
 * the class components in between.
 */
export const useSortableNode = () => useContext(SortableNodeContext);

interface SortableNodeProviderProps extends React.PropsWithChildren {
  id: string;
  disabled?: boolean;
}

export const SortableNodeProvider = ({ id, disabled, children }: SortableNodeProviderProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id, disabled });

  const node: SortableNode = {
    setNodeRef,
    style: {
      transform: CSS.Transform.toString(transform),
      transition,
      zIndex: isDragging ? 1 : undefined,
    },
    handleProps: { ...attributes, ...listeners },
  };

  return <SortableNodeContext.Provider value={node}>{children}</SortableNodeContext.Provider>;
};

/** Makes a component sortable by the `id` prop it is given. */
export function withSortable<Props extends { id: string }>(Component: React.ComponentType<Props>) {
  const Sortable = (props: Props) => (
    <SortableNodeProvider id={props.id}>
      <Component {...props} />
    </SortableNodeProvider>
  );

  Sortable.displayName = `withSortable(${Component.displayName || Component.name || 'Component'})`;

  return Sortable;
}
