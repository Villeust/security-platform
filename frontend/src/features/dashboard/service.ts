import { api } from '../../services/api';
import type { DashboardPeriodKey, DashboardResponse } from './types';

export async function getDashboard(period: DashboardPeriodKey, signal?: AbortSignal) {
  const response = await api.get<DashboardResponse>('/api/v1/dashboard', {
    params: { period, recent_limit: 8 },
    signal,
  });
  return response.data;
}
