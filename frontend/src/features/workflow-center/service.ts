import { api } from '../../services/api';
import type {
  ListResponse,
  OutboxMonitor,
  PlatformHealth,
  ProcessAuditItem,
  SlaCenter,
  Uuid,
  WorkflowDashboard,
  WorkflowDefinition,
  WorkflowDefinitionDetail,
  WorkflowInstance,
  WorkflowInstanceDetail,
  WorkflowSearchResult,
  WorkflowStatistics,
  WorkflowValidation,
  WorkflowVersion,
  WorkflowVersionDiff,
} from './types';

const base = '/api/v1/admin/workflow-center';

export async function getWorkflowDashboard() {
  const response = await api.get<WorkflowDashboard>(`${base}/dashboard`);
  return response.data;
}

export async function getWorkflowDefinitions(params: Record<string, unknown> = {}) {
  const response = await api.get<ListResponse<WorkflowDefinition>>(`${base}/definitions`, { params });
  return response.data;
}

export async function getWorkflowDefinition(id: Uuid) {
  const response = await api.get<WorkflowDefinitionDetail>(`${base}/definitions/${id}`);
  return response.data;
}

export async function createWorkflowDefinition(payload: { code: string; name: string; description?: string | null; entity_type: string }) {
  const response = await api.post<WorkflowDefinitionDetail>(`${base}/definitions`, payload);
  return response.data;
}

export async function updateWorkflowDefinition(id: Uuid, payload: { name?: string; description?: string | null; is_active?: boolean }) {
  const response = await api.patch<WorkflowDefinitionDetail>(`${base}/definitions/${id}`, payload);
  return response.data;
}

export async function createWorkflowVersion(id: Uuid) {
  const response = await api.post<WorkflowDefinitionDetail>(`${base}/definitions/${id}/versions`);
  return response.data;
}

export async function publishWorkflowDefinition(id: Uuid) {
  const response = await api.post<WorkflowDefinitionDetail>(`${base}/definitions/${id}/publish`);
  return response.data;
}

export async function deactivateWorkflowDefinition(id: Uuid) {
  const response = await api.post<WorkflowDefinitionDetail>(`${base}/definitions/${id}/deactivate`);
  return response.data;
}

export async function validateWorkflowDefinition(id: Uuid) {
  const response = await api.get<WorkflowValidation>(`${base}/definitions/${id}/validation`);
  return response.data;
}

export async function getWorkflowVersions(params: Record<string, unknown> = {}) {
  const response = await api.get<ListResponse<WorkflowVersion>>(`${base}/versions`, { params });
  return response.data;
}

export async function getWorkflowVersionDiff(sourceId: Uuid, targetId: Uuid) {
  const response = await api.get<WorkflowVersionDiff>(`${base}/versions/diff`, { params: { source_id: sourceId, target_id: targetId } });
  return response.data;
}

export async function getWorkflowInstances(params: Record<string, unknown> = {}) {
  const response = await api.get<ListResponse<WorkflowInstance>>(`${base}/instances`, { params });
  return response.data;
}

export async function getWorkflowInstance(id: Uuid) {
  const response = await api.get<WorkflowInstanceDetail>(`${base}/instances/${id}`);
  return response.data;
}

export async function getSlaCenter() {
  const response = await api.get<SlaCenter>(`${base}/sla`);
  return response.data;
}

export async function getOutboxMonitor(params: Record<string, unknown> = {}) {
  const response = await api.get<OutboxMonitor>(`${base}/outbox`, { params });
  return response.data;
}

export async function getProcessAudit(params: Record<string, unknown> = {}) {
  const response = await api.get<ListResponse<ProcessAuditItem>>(`${base}/audit`, { params });
  return response.data;
}

export async function getWorkflowStatistics() {
  const response = await api.get<WorkflowStatistics>(`${base}/statistics`);
  return response.data;
}

export async function getPlatformHealth() {
  const response = await api.get<PlatformHealth>(`${base}/health`);
  return response.data;
}

export async function searchWorkflowCenter(q: string) {
  const response = await api.get<{ items: WorkflowSearchResult[] }>(`${base}/search`, { params: { q } });
  return response.data.items;
}
