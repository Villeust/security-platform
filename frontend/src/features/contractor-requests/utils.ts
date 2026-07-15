import type { Contractor, Facility, Uuid, WorkType } from './types/api';

export function formatDate(value: string | null | undefined) {
  if (!value) {
    return '—';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function getWorkTypeLabel(workType: WorkType | undefined) {
  if (!workType) {
    return '—';
  }
  if (workType.code === 'ACCESS_CONTROL') {
    return 'СКУД';
  }
  if (workType.code === 'CCTV') {
    return 'СВН';
  }
  return workType.name;
}

export function labelsByIds<T extends { id: Uuid }>(
  ids: Uuid[],
  records: T[],
  getLabel: (record: T) => string,
) {
  return ids
    .map((id) => records.find((record) => record.id === id))
    .filter((record): record is T => Boolean(record))
    .map(getLabel);
}

export function facilityName(id: Uuid, facilities: Facility[]) {
  return facilities.find((facility) => facility.id === id)?.name ?? '—';
}

export function contractorName(id: Uuid, contractors: Contractor[]) {
  return contractors.find((contractor) => contractor.id === id)?.name ?? '—';
}
