import dayjs from 'dayjs';
import { default_working_hours } from './WorkingHours.config';
import { getWorkingMoments } from './WorkingHours.helpers';

it('reuses working-hour cache entries independently of object property order', () => {
  const start = dayjs.utc('2026-11-16T00:00:00Z');
  const end = start.add(1, 'day');
  const hours = default_working_hours;
  const reordered = Object.fromEntries(
    Object.entries(hours)
      .reverse()
      .map(([day, ranges]) => [day, ranges.map(({ start, end }) => ({ start, end }))])
  ) as typeof hours;
  expect(getWorkingMoments(start, end, reordered, 'UTC')).toBe(getWorkingMoments(start, end, hours, 'UTC'));
});

it('does not reuse a cached result when working-hour boundaries change', () => {
  const start = dayjs.utc('2026-11-16T00:00:00Z');
  const end = start.add(1, 'day');
  const original = getWorkingMoments(start, end, default_working_hours, 'UTC');
  const changed = getWorkingMoments(
    start,
    end,
    { ...default_working_hours, monday: [{ start: '10:00:00', end: '12:00:00' }] },
    'UTC'
  );
  expect(changed).not.toBe(original);
  expect(changed[0].start.format('HH:mm')).toBe('10:00');
  expect(changed[0].end.format('HH:mm')).toBe('12:00');
});
