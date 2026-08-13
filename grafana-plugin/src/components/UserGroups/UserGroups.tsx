import React, { useCallback, useEffect, useMemo, useRef } from 'react';

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
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { cx } from '@emotion/css';
import { Stack, IconButton, useStyles2 } from '@grafana/ui';
import { UserActions } from 'helpers/authorization/authorization';
import { bem } from 'styles/utils.styles';

import { SortableNodeProvider, useSortableNode } from 'components/SortableList/SortableNode';
import { Text } from 'components/Text/Text';
import { RemoteSelect } from 'containers/RemoteSelect/RemoteSelect';
import { ApiSchemas } from 'network/oncall-api/api.types';

import { fromPlainArray, toPlainArray } from './UserGroups.helpers';
import { getUserGroupStyles } from './UserGroups.styles';
import { Item } from './UserGroups.types';

interface UserGroupsProps {
  value: Array<Array<ApiSchemas['User']['pk']>>;
  onChange: (value: Array<Array<ApiSchemas['User']['pk']>>) => void;
  isMultipleGroups: boolean;
  renderUser: (id: string) => React.ReactElement;
  showError?: boolean;
  disabled?: boolean;
}

const DragHandle = () => {
  const { handleProps } = useSortableNode();

  return <IconButton {...handleProps} aria-label="Drag" className={cx('icon')} name="draggabledots" />;
};

/** the row that moves while dragging; picks its sortable wiring up from context */
const SortableRow = ({ className, onClick, children }: React.PropsWithChildren<{ className: string; onClick?: () => void }>) => {
  const { setNodeRef, style } = useSortableNode();

  return (
    <li ref={setNodeRef} style={style} className={className} onClick={onClick}>
      {children}
    </li>
  );
};

export const UserGroups = (props: UserGroupsProps) => {
  const styles = useStyles2(getUserGroupStyles);
  const { value, onChange, isMultipleGroups, renderUser, showError, disabled } = props;

  const handleAddUserGroup = useCallback(() => {
    onChange([...value, []]);
  }, [value]);

  const handleDeleteUser = (index: number) => {
    const newGroups = [...value];
    let k = -1;
    for (let i = 0; i < value.length; i++) {
      k++;
      const users = value[i];
      for (let j = 0; j < users.length; j++) {
        k++;

        if (k === index) {
          newGroups[i] = newGroups[i].filter((_item, itemIndex) => itemIndex !== j);
          onChange(newGroups.filter((group) => group.length));
          return;
        }
      }
    }
  };

  const handleUserAdd = useCallback(
    (pk: ApiSchemas['User']['pk']) => {
      if (!pk) {
        return;
      }

      const newGroups = [...value];
      let lastGroup = newGroups[newGroups.length - 1];
      if (!isMultipleGroups || (lastGroup && !lastGroup.length)) {
        if (!lastGroup) {
          lastGroup = [];
          newGroups.push(lastGroup);
        }
        lastGroup.push(pk);
      } else {
        newGroups.push([pk]);
      }

      onChange(newGroups);
    },
    [value]
  );

  const items = useMemo(() => toPlainArray(value), [value]);

  const onSortEnd = useCallback(
    ({ oldIndex, newIndex }: { oldIndex: number; newIndex: number }) => {
      const newPlainArray = arrayMove(items, oldIndex, newIndex);

      onChange(fromPlainArray(newPlainArray, newIndex > items.length));
    },
    [items]
  );

  const getDeleteItemHandler = (index: number) => {
    return () => {
      handleDeleteUser(index);
    };
  };

  const renderItem = (item: Item, index: number) => (
    <SortableRow className={styles.user}>
      {renderUser(item.data)}
      {!disabled && (
        <div className={styles.userButtons}>
          <Stack>
            <IconButton
              aria-label="Remove"
              className={styles.icon}
              name="trash-alt"
              onClick={getDeleteItemHandler(index)}
            />
            <DragHandle />
          </Stack>
        </div>
      )}
    </SortableRow>
  );

  return (
    <div className={styles.root}>
      <Stack direction="column">
        {!disabled && (
          <RemoteSelect
            key={items.length}
            showSearch
            placeholder="Add user"
            href={`/users/?permission=${UserActions.NotificationsRead.permission}&filters=true`}
            value={null}
            onChange={handleUserAdd}
            showError={showError}
            maxMenuHeight={150}
            requiredUserAction={UserActions.UserSettingsWrite}
          />
        )}
        <SortableList
          renderItem={renderItem}
          items={items}
          onSortEnd={onSortEnd}
          handleAddGroup={handleAddUserGroup}
          isMultipleGroups={isMultipleGroups}
          allowCreate={!disabled}
        />
      </Stack>
    </div>
  );
};

interface SortableListProps {
  items: Item[];
  handleAddGroup: () => void;
  isMultipleGroups: boolean;
  renderItem: (item: Item, index: number) => React.ReactElement;
  onSortEnd: (indexes: { oldIndex: number; newIndex: number }) => void;
  allowCreate?: boolean;
}

export const SortableList = ({
  items,
  handleAddGroup,
  isMultipleGroups,
  renderItem,
  onSortEnd,
  allowCreate,
}: SortableListProps) => {
  const listRef = useRef<HTMLUListElement>();
  const styles = useStyles2(getUserGroupStyles);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  useEffect(() => {
    const container = listRef.current;

    container.scroll({
      left: 0,
      top: container.scrollHeight,
      behavior: 'smooth',
    });
  }, [items]);

  const handleDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) {
      return;
    }

    const keys = items.map((item) => item.key);
    onSortEnd({ oldIndex: keys.indexOf(String(active.id)), newIndex: keys.indexOf(String(over.id)) });
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      modifiers={[restrictToVerticalAxis]}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={items.map((item) => item.key)} strategy={verticalListSortingStrategy}>
        <ul className={styles.groups} ref={listRef}>
          {items.map((item, index) =>
            item.type === 'item' ? (
              <SortableNodeProvider key={item.key} id={item.key}>
                {renderItem(item, index)}
              </SortableNodeProvider>
            ) : isMultipleGroups ? (
              <SortableNodeProvider key={item.key} id={item.key}>
                <SortableRow className={styles.separator}>
                  <Text type="secondary">{item.data.name}</Text>
                </SortableRow>
              </SortableNodeProvider>
            ) : null
          )}
          {allowCreate && isMultipleGroups && items[items.length - 1]?.type === 'item' && (
            <li
              onClick={handleAddGroup}
              className={cx(styles.separator, { [bem(styles.separator, 'clickable')]: true })}
            >
              <Text type="primary">+ Add user group</Text>
            </li>
          )}
        </ul>
      </SortableContext>
    </DndContext>
  );
};
