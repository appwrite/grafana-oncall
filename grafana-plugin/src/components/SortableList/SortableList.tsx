import React from 'react';

import {
  closestCenter,
  DndContext,
  DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { restrictToVerticalAxis } from '@dnd-kit/modifiers';
import { SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy } from '@dnd-kit/sortable';

import { Timeline } from 'components/Timeline/Timeline';

interface SortableListProps extends React.PropsWithChildren {
  /** ids of the sortable children, in the order they are rendered */
  items: string[];
  onSortEnd: (indexes: { oldIndex: number; newIndex: number }) => void;
  className?: string;
}

export const SortableList = ({ items, onSortEnd, className, children }: SortableListProps) => {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) {
      return;
    }

    onSortEnd({ oldIndex: items.indexOf(String(active.id)), newIndex: items.indexOf(String(over.id)) });
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[restrictToVerticalAxis]}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={items} strategy={verticalListSortingStrategy}>
        <Timeline className={className}>{children}</Timeline>
      </SortableContext>
    </DndContext>
  );
};
