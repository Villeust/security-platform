export const requestStatusLabel: Record<string, string> = {
  DRAFT: 'Черновик',
  NEW: 'Новая',
  PARTIALLY_ASSIGNED: 'Частично назначена',
  ASSIGNED: 'Назначена',
  IN_PROGRESS: 'В работе',
  COMPLETED: 'Выполнена',
  CLOSED: 'Закрыта',
  CANCELLED: 'Отменена',
};

export const priorityLabel: Record<string, string> = {
  LOW: 'Низкий',
  MEDIUM: 'Средний',
  HIGH: 'Высокий',
  CRITICAL: 'Критический',
};

export const roleLabel: Record<string, string> = {
  PLATFORM_ADMIN: 'Администратор платформы',
  SECURITY_ADMIN: 'Администратор безопасности',
  SECURITY_OPERATOR: 'Оператор безопасности',
  VIEWER: 'Наблюдатель',
};

export const serviceStatusLabel: Record<string, string> = {
  works: 'Работает',
  configured: 'Настроено',
  not_configured: 'Не настроено',
  limited: 'Ограничено',
  unavailable: 'Недоступно',
  planned: 'Планируется',
};

export function formatDate(value?: string | null, withTime = false) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('ru-RU', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' }).format(new Date(value));
}

export function relativeDeadline(value: string) {
  const target = new Date(value);
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  const targetStart = new Date(target.getFullYear(), target.getMonth(), target.getDate()).getTime();
  const diffDays = Math.round((targetStart - start) / 86400000);
  if (diffDays === 0) return 'сегодня';
  if (diffDays === 1) return 'завтра';
  if (diffDays > 1) return `через ${diffDays} дн.`;
  return `просрочено на ${Math.abs(diffDays)} дн.`;
}
