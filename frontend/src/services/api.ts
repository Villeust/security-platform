import axios from 'axios';

import { appConfig } from '../config';

export const api = axios.create({
  baseURL: appConfig.apiUrl,
  timeout: 5000,
});

api.interceptors.request.use((config) => {
  const devSelectorEnabled = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_USER_SELECTOR === 'true';
  const userId = (devSelectorEnabled ? localStorage.getItem('security-platform.devUserId') : null) ?? import.meta.env.VITE_DEV_USER_ID;
  if (userId) {
    config.headers.set('X-User-Id', userId);
  }
  return config;
});
