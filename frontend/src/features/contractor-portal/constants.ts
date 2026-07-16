import type { AssignmentStatus, RequestAttachmentCategory, RequestHistoryEventType, RequestStatus } from '../contractor-requests/types/api';

export const requestStatusLabel: Record<RequestStatus, string> = {
  DRAFT: 'Черновик',
  NEW: 'Новая',
  PARTIALLY_ASSIGNED: 'Частично назначена',
  ASSIGNED: 'Назначена',
  IN_PROGRESS: 'В работе',
  COMPLETED: 'Выполнена',
  CLOSED: 'Закрыта',
  CANCELLED: 'Отменена',
};

export const assignmentStatusLabel: Record<AssignmentStatus, string> = {
  ASSIGNED: 'Назначено',
  ACCEPTED: 'Принято',
  IN_PROGRESS: 'В работе',
  COMPLETED: 'Выполнено',
  CANCELLED: 'Отменено',
};

export const priorityLabel: Record<string, string> = {
  LOW: 'Низкий',
  MEDIUM: 'Средний',
  HIGH: 'Высокий',
  CRITICAL: 'Критический',
};

export const roleLabel: Record<string, string> = {
  CONTRACTOR_MANAGER: 'Менеджер подрядчика',
  CONTRACTOR_USER: 'Пользователь подрядчика',
  LEGACY_DEV_CONTRACTOR: 'Подрядчик',
};

export const authSourceLabel: Record<string, string> = {
  LOCAL: 'Локальная учётная запись',
  LDAP: 'Корпоративный каталог',
  ADFS: 'ADFS',
};

export const fileCategoryLabel: Record<RequestAttachmentCategory, string> = {
  REQUEST_FILE: 'Файл заявки',
  WORK_RESULT: 'Результат работ',
  ACT: 'Акт',
  PHOTO: 'Фото',
  DOCUMENT: 'Документ',
  OTHER: 'Другое',
};

export const historyEventLabel: Record<RequestHistoryEventType, string> = {
  CREATED: 'Создана',
  UPDATED: 'Обновлена',
  PUBLISHED: 'Опубликована',
  STATUS_CHANGED: 'Статус изменён',
  ASSIGNMENT_CREATED: 'Назначение создано',
  ASSIGNMENT_ACCEPTED: 'Назначение принято',
  ASSIGNMENT_STATUS_CHANGED: 'Статус назначения изменён',
  REOPENED: 'Возвращена в работу',
  CLOSED: 'Закрыта',
  CANCELLED: 'Отменена',
  COMMENT_ADDED: 'Комментарий добавлен',
  COMMENT_UPDATED: 'Комментарий обновлён',
  COMMENT_DELETED: 'Комментарий удалён',
  ATTACHMENT_ADDED: 'Вложение добавлено',
  ATTACHMENT_DELETED: 'Вложение удалено',
  WORK_RESULT_ADDED: 'Результат работ добавлен',
};

export function requestTone(status: RequestStatus) {
  if (status === 'COMPLETED' || status === 'CLOSED') return 'success';
  if (status === 'CANCELLED') return 'error';
  if (status === 'IN_PROGRESS') return 'processing';
  return 'warning';
}

export function assignmentTone(status: AssignmentStatus) {
  if (status === 'COMPLETED') return 'success';
  if (status === 'CANCELLED') return 'error';
  if (status === 'IN_PROGRESS' || status === 'ACCEPTED') return 'processing';
  return 'warning';
}

export function formatDate(value?: string | null, withTime = false) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('ru-RU', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' }).format(new Date(value));
}

export function isOverdue(value?: string | null) {
  return Boolean(value && new Date(value).getTime() < Date.now());
}
