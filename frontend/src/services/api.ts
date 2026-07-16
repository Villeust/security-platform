import axios from 'axios';

import { appConfig } from '../config';

const DEV_USER_HEADER = 'X-User-Id';

export const api = axios.create({
  baseURL: appConfig.apiUrl,
  timeout: 5000,
  withCredentials: true,
});

let refreshing: Promise<void> | null = null;

function cookieValue(name: string) {
  return document.cookie
    .split('; ')
    .find((part) => part.startsWith(`${name}=`))
    ?.split('=')
    .slice(1)
    .join('=');
}

export function setDevUserHeader(userId: string | null) {
  if (userId) {
    api.defaults.headers.common[DEV_USER_HEADER] = userId;
  } else {
    delete api.defaults.headers.common[DEV_USER_HEADER];
  }
}

api.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase();
  if (method && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = cookieValue('sp_csrf');
    if (csrf) {
      config.headers.set('X-CSRF-Token', decodeURIComponent(csrf));
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || original?._retry || original?.url?.includes('/auth/login') || original?.url?.includes('/auth/refresh')) {
      return Promise.reject(error);
    }
    original._retry = true;
    refreshing ??= api.post('/api/v1/auth/refresh').then(() => undefined).finally(() => {
      refreshing = null;
    });
    await refreshing;
    return api(original);
  },
);
