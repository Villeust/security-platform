import axios from 'axios';

import { appConfig } from '../config';

export const api = axios.create({
  baseURL: appConfig.apiUrl,
  timeout: 5000,
});
