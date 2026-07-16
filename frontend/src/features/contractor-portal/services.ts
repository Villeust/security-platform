import { api } from '../../services/api';
import type { ContractorRequest, RequestAttachment, RequestComment, RequestHistoryItem } from '../contractor-requests/types/api';
import type { ContractorDashboard, ContractorMe, ContractorNotification, ContractorRequestFilters, ContractorTask } from './types';

const base = '/api/v1/contractor';

export async function getContractorMe() {
  const response = await api.get<ContractorMe>(`${base}/me`);
  return response.data;
}

export async function getContractorProfile() {
  const response = await api.get<ContractorMe>(`${base}/profile`);
  return response.data;
}

export async function getContractorDashboard() {
  const response = await api.get<ContractorDashboard>(`${base}/dashboard`);
  return response.data;
}

export async function getContractorRequests(params: ContractorRequestFilters = {}) {
  const response = await api.get<ContractorRequest[]>(`${base}/requests`, { params: { limit: 50, ...params } });
  return response.data;
}

export async function getContractorRequest(requestId: string) {
  const response = await api.get<ContractorRequest>(`${base}/requests/${requestId}`);
  return response.data;
}

export async function acceptContractorRequest(requestId: string) {
  const response = await api.post<ContractorRequest>(`${base}/requests/${requestId}/accept`);
  return response.data;
}

export async function updateContractorAssignmentStatus(assignmentId: string, status: string, comment?: string) {
  const response = await api.post<ContractorTask>(`${base}/assignments/${assignmentId}/status`, { status, comment: comment ?? null });
  return response.data;
}

export async function getContractorTasks(status?: string) {
  const response = await api.get<ContractorTask[]>(`${base}/tasks`, { params: { status } });
  return response.data;
}

export async function getContractorNotifications() {
  const response = await api.get<ContractorNotification[]>(`${base}/notifications`);
  return response.data;
}

export async function getContractorRequestComments(requestId: string) {
  const response = await api.get<RequestComment[]>(`${base}/requests/${requestId}/comments`);
  return response.data;
}

export async function createContractorRequestComment(requestId: string, body: string) {
  const response = await api.post<RequestComment>(`${base}/requests/${requestId}/comments`, { body, visibility: 'SHARED' });
  return response.data;
}

export async function getContractorRequestAttachments(requestId: string) {
  const response = await api.get<RequestAttachment[]>(`${base}/requests/${requestId}/attachments`);
  return response.data;
}

export async function getContractorRequestHistory(requestId: string) {
  const response = await api.get<RequestHistoryItem[]>(`${base}/requests/${requestId}/history`);
  return response.data;
}
