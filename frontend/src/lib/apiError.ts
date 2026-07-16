import { isAxiosError } from 'axios';

import { getLastCorrelationId } from './correlation';

export type NormalizedErrorKind =
  | 'authentication'
  | 'authorization'
  | 'not_found'
  | 'conflict'
  | 'payload_too_large'
  | 'validation'
  | 'server'
  | 'csrf_expired'
  | 'session_expired'
  | 'password_change_required'
  | 'offline'
  | 'timeout'
  | 'network'
  | 'unknown';

export type NormalizedApiError = {
  kind: NormalizedErrorKind;
  status?: number;
  code?: string;
  title: string;
  message: string;
  detail?: unknown;
  correlationId?: string | null;
  path?: string;
  original: unknown;
};

type StandardErrorPayload = {
  detail?: unknown;
  correlation_id?: string;
  path?: string;
  error?: {
    code?: string;
    message?: string;
    detail?: unknown;
  };
};

const messages: Record<NormalizedErrorKind, string> = {
  authentication: 'Сессия устарела. Выполните вход повторно.',
  authorization: 'Недостаточно прав для выполнения действия.',
  not_found: 'Запрошенные данные не найдены.',
  conflict: 'Данные были изменены. Обновите страницу и повторите действие.',
  payload_too_large: 'Файл или запрос слишком большой.',
  validation: 'Проверьте заполненные поля.',
  server: 'Сервис временно недоступен. Попробуйте позже.',
  csrf_expired: 'Сессия безопасности устарела. Обновите страницу и повторите действие.',
  session_expired: 'Сессия устарела. Выполните вход повторно.',
  password_change_required: 'Необходимо сменить временный пароль.',
  offline: 'Нет подключения к сети.',
  timeout: 'Превышено время ожидания ответа.',
  network: 'Не удалось подключиться к серверу.',
  unknown: 'Что-то пошло не так.',
};

function detailToMessage(detail: unknown) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) return messages.validation;
  return undefined;
}

function kindFor(status?: number, code?: string, detail?: unknown): NormalizedErrorKind {
  const text = typeof detail === 'string' ? detail : '';
  if (code === 'CSRF_TOKEN_INVALID' || text.includes('CSRF')) return 'csrf_expired';
  if (code === 'PASSWORD_CHANGE_REQUIRED' || text === 'PASSWORD_CHANGE_REQUIRED') return 'password_change_required';
  if (status === 401) return 'session_expired';
  if (status === 403) return 'authorization';
  if (status === 404) return 'not_found';
  if (status === 409) return 'conflict';
  if (status === 413) return 'payload_too_large';
  if (status === 422) return 'validation';
  if (status && status >= 500) return 'server';
  return 'unknown';
}

export function parseApiError(error: unknown): NormalizedApiError {
  if (isAxiosError(error)) {
    const status = error.response?.status;
    const payload = error.response?.data as StandardErrorPayload | undefined;
    const code = payload?.error?.code;
    const detail = payload?.error?.message ?? payload?.error?.detail ?? payload?.detail;
    const correlationId = error.response?.headers?.['x-correlation-id'] ?? payload?.correlation_id ?? getLastCorrelationId();

    if (error.code === 'ECONNABORTED') {
      return { kind: 'timeout', title: 'Таймаут запроса', message: messages.timeout, correlationId, original: error };
    }
    if (!error.response) {
      const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
      const kind: NormalizedErrorKind = offline ? 'offline' : 'network';
      return { kind, title: offline ? 'Нет сети' : 'Сеть недоступна', message: messages[kind], correlationId, original: error };
    }

    const kind = kindFor(status, code, detail);
    return {
      kind,
      status,
      code,
      title: status ? `Ошибка ${status}` : 'Ошибка запроса',
      message: detailToMessage(detail) ?? messages[kind],
      detail,
      correlationId,
      path: payload?.path,
      original: error,
    };
  }

  return {
    kind: 'unknown',
    title: 'Ошибка приложения',
    message: error instanceof Error ? error.message : messages.unknown,
    correlationId: getLastCorrelationId(),
    original: error,
  };
}

export function errorToastKey(error: NormalizedApiError) {
  return [error.kind, error.status ?? '', error.code ?? '', error.message, error.correlationId ?? ''].join('|');
}
