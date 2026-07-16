import { api } from '../../../services/api';
import type { ContractorRequest, CreateContractorRequestPayload, RequestHistoryItem, RequestListParams, RequestStatus, Uuid } from '../types/api';

export async function getRequests(params: RequestListParams = {}, signal?: AbortSignal) {
  const response = await api.get<ContractorRequest[]>('/api/v1/requests', { params: { limit: 100, ...params }, signal });
  return response.data;
}

export async function getRequest(requestId: Uuid, signal?: AbortSignal) {
  const response = await api.get<ContractorRequest>(`/api/v1/requests/${requestId}`, { signal });
  return response.data;
}

export async function createRequest(payload: CreateContractorRequestPayload) {
  const response = await api.post<ContractorRequest>('/api/v1/requests', payload);
  return response.data;
}

export async function publishRequest(requestId: Uuid) {
  const response = await api.post<ContractorRequest>(`/api/v1/requests/${requestId}/publish`);
  return response.data;
}

export async function updateRequestStatus(requestId: Uuid, status: RequestStatus, comment?: string | null) {
  const response = await api.post<ContractorRequest>(`/api/v1/requests/${requestId}/status`, { status, comment: comment ?? null });
  return response.data;
}

export async function getRequestHistory(requestId: Uuid, signal?: AbortSignal) {
  const response = await api.get<RequestHistoryItem[]>(`/api/v1/requests/${requestId}/history`, { signal });
  return response.data;
}
