const STORAGE_KEY = 'security-platform.lastCorrelationId';

let lastCorrelationId: string | null = null;

export function setLastCorrelationId(value: string | null | undefined) {
  if (!value) return;
  lastCorrelationId = value;
  try {
    sessionStorage.setItem(STORAGE_KEY, value);
  } catch {
    // Session storage may be unavailable in restricted browser contexts.
  }
  if (import.meta.env.DEV) {
    console.info(`[Security Platform] correlation_id=${value}`);
  }
}

export function getLastCorrelationId() {
  if (lastCorrelationId) return lastCorrelationId;
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export async function copyCorrelationId(value = getLastCorrelationId()) {
  if (!value || !navigator.clipboard) return false;
  await navigator.clipboard.writeText(value);
  return true;
}
