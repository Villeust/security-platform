import { message } from 'antd';

import { errorToastKey, parseApiError, type NormalizedApiError } from './apiError';

const DEFAULT_WINDOW_MS = 3500;
const recent = new Map<string, number>();

export function shouldNotify(key: string, now = Date.now(), windowMs = DEFAULT_WINDOW_MS) {
  const previous = recent.get(key);
  if (previous && now - previous < windowMs) return false;
  recent.set(key, now);
  for (const [storedKey, timestamp] of recent) {
    if (now - timestamp > windowMs * 2) recent.delete(storedKey);
  }
  return true;
}

export function notifyApiError(error: unknown, fallback?: string) {
  const parsed = parseApiError(error);
  notifyNormalizedError(parsed, fallback);
  return parsed;
}

export function notifyNormalizedError(error: NormalizedApiError, fallback?: string) {
  const key = errorToastKey(error);
  if (!shouldNotify(key)) return;
  message.error(fallback ?? error.message);
}

export function notifySuccess(text: string) {
  message.success(text);
}

export function resetToastDedupe() {
  recent.clear();
}
