const apiUrl = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '');

if (!apiUrl) {
  console.warn('VITE_API_URL is not configured; API requests will use the current origin.');
}

export const appConfig = {
  apiUrl: apiUrl ?? '',
};
