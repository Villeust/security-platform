const apiUrl = import.meta.env.VITE_API_URL;

if (!apiUrl) {
  console.warn('VITE_API_URL is not configured; API requests will use the current origin.');
}

export const appConfig = {
  apiUrl: apiUrl ?? '',
};
