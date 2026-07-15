import { api } from '../../../services/api';
import type { ContractorRequest, CreateContractorRequestPayload, Uuid } from '../types/api';

export async function getRequests() {
  const response = await api.get<ContractorRequest[]>('/api/v1/requests', { params: { limit: 100 } });
  return response.data;
}

export async function getRequest(requestId: Uuid) {
  const response = await api.get<ContractorRequest>(`/api/v1/requests/${requestId}`);
  return response.data;
}

export async function createRequest(payload: CreateContractorRequestPayload) {
  const response = await api.post<ContractorRequest>('/api/v1/requests', payload);
  return response.data;
}
