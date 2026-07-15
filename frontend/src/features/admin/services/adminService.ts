import { api } from '../../../services/api';
import type {
  AdminContractor,
  AdminDashboard,
  AdminListParams,
  AdminNotification,
  AdminUser,
  AuthProviderStatus,
  AuditLog,
  AuthGroupMapping,
  ConnectionConfiguration,
  ConnectionEventLog,
  ConnectionProviderType,
  ConnectionTestResponse,
  DirectoryGroup,
  LoginResponse,
  Permission,
  Role,
  SystemStatus,
  UserCreateResponse,
  Uuid,
} from '../types';

export async function getCurrentUser() {
  const response = await api.get<AdminUser>('/api/v1/admin/me');
  return response.data;
}

export async function getAuthMe() {
  const response = await api.get<AdminUser>('/api/v1/auth/me');
  return response.data;
}

export async function getAuthProviders() {
  const response = await api.get<AuthProviderStatus[]>('/api/v1/auth/providers');
  return response.data;
}

export async function login(payload: { username: string; password: string; provider?: 'LOCAL' | 'LDAP' }) {
  const response = await api.post<LoginResponse>('/api/v1/auth/login', { provider: 'LOCAL', ...payload });
  return response.data;
}

export async function logout() {
  await api.post('/api/v1/auth/logout');
}

export async function changePassword(currentPassword: string, newPassword: string) {
  await api.post('/api/v1/auth/change-password', { current_password: currentPassword, new_password: newPassword });
}

export async function getDevUsers() {
  const response = await api.get<AdminUser[]>('/api/v1/admin/dev-users');
  return response.data;
}

export async function getAdminDashboard() {
  const response = await api.get<AdminDashboard>('/api/v1/admin/dashboard');
  return response.data;
}

export async function getSystemStatus() {
  const response = await api.get<SystemStatus>('/api/v1/admin/system-status');
  return response.data;
}

export async function getContractors(params: AdminListParams = {}) {
  const response = await api.get<AdminContractor[]>('/api/v1/admin/contractors', { params: { limit: 100, ...params } });
  return response.data;
}

export async function createContractor(payload: Partial<AdminContractor>) {
  const response = await api.post<AdminContractor>('/api/v1/admin/contractors', payload);
  return response.data;
}

export async function updateContractor(id: Uuid, payload: Partial<AdminContractor>) {
  const response = await api.patch<AdminContractor>(`/api/v1/admin/contractors/${id}`, payload);
  return response.data;
}

export async function setContractorActive(id: Uuid, active: boolean) {
  const response = await api.post<AdminContractor>(`/api/v1/admin/contractors/${id}/${active ? 'activate' : 'deactivate'}`);
  return response.data;
}

export async function getUsers(params: AdminListParams = {}) {
  const response = await api.get<AdminUser[]>('/api/v1/admin/users', { params: { limit: 100, ...params } });
  return response.data;
}

export async function createUser(payload: Record<string, unknown>) {
  const response = await api.post<UserCreateResponse>('/api/v1/admin/users', payload);
  return response.data;
}

export async function generateTemporaryPassword(id: Uuid) {
  const response = await api.post<UserCreateResponse>(`/api/v1/admin/users/${id}/generate-temporary-password`);
  return response.data;
}

export async function setUserLocked(id: Uuid, locked: boolean, comment?: string) {
  const response = await api.post<AdminUser>(`/api/v1/admin/users/${id}/${locked ? 'lock' : 'unlock'}`, locked ? { reason: 'ADMINISTRATIVE', comment } : { comment });
  return response.data;
}

export async function updateUser(id: Uuid, payload: Record<string, unknown>) {
  const response = await api.patch<AdminUser>(`/api/v1/admin/users/${id}`, payload);
  return response.data;
}

export async function setUserActive(id: Uuid, active: boolean) {
  const response = await api.post<AdminUser>(`/api/v1/admin/users/${id}/${active ? 'activate' : 'deactivate'}`);
  return response.data;
}

export async function setUserRoles(id: Uuid, roleIds: Uuid[]) {
  const response = await api.put<AdminUser>(`/api/v1/admin/users/${id}/roles`, { role_ids: roleIds });
  return response.data;
}

export async function setUserContractors(id: Uuid, contractorIds: Uuid[]) {
  const response = await api.put<AdminUser>(`/api/v1/admin/users/${id}/contractors`, {
    contractor_memberships: contractorIds.map((contractor_id, index) => ({ contractor_id, is_primary: index === 0, is_active: true })),
  });
  return response.data;
}

export async function getRoles(params: AdminListParams = {}) {
  const response = await api.get<Role[]>('/api/v1/admin/roles', { params: { limit: 100, ...params } });
  return response.data;
}

export async function getPermissions() {
  const response = await api.get<Permission[]>('/api/v1/admin/permissions');
  return response.data;
}

export async function getRolePermissions(roleId: Uuid) {
  const response = await api.get<Permission[]>(`/api/v1/admin/roles/${roleId}/permissions`);
  return response.data;
}

export async function setRolePermissions(roleId: Uuid, permissionIds: Uuid[]) {
  const response = await api.put<Permission[]>(`/api/v1/admin/roles/${roleId}/permissions`, { permission_ids: permissionIds });
  return response.data;
}

export async function createRole(payload: Partial<Role>) {
  const response = await api.post<Role>('/api/v1/admin/roles', payload);
  return response.data;
}

export async function updateRole(id: Uuid, payload: Partial<Role>) {
  const response = await api.patch<Role>(`/api/v1/admin/roles/${id}`, payload);
  return response.data;
}

export async function deactivateRole(id: Uuid) {
  const response = await api.post<Role>(`/api/v1/admin/roles/${id}/deactivate`);
  return response.data;
}

export async function getAudit(params: AdminListParams = {}) {
  const response = await api.get<AuditLog[]>('/api/v1/admin/audit', { params: { limit: 100, ...params } });
  return response.data;
}

export async function getAdminReference<T>(resource: string, params: AdminListParams = {}) {
  const response = await api.get<T[]>(`/api/v1/admin/${resource}`, { params: { limit: 100, ...params } });
  return response.data;
}

export async function getNotifications(params: AdminListParams = {}) {
  const response = await api.get<AdminNotification[]>('/api/v1/admin/notifications', { params: { limit: 100, ...params } });
  return response.data;
}

export async function getUnreadNotificationsCount() {
  const response = await api.get<{ count: number }>('/api/v1/admin/notifications/unread-count');
  return response.data.count;
}

export async function markNotificationRead(id: Uuid) {
  const response = await api.post<AdminNotification>(`/api/v1/admin/notifications/${id}/read`);
  return response.data;
}

export async function resolveNotification(id: Uuid) {
  const response = await api.post<AdminNotification>(`/api/v1/admin/notifications/${id}/resolve`);
  return response.data;
}

export async function getConnectionConfig(provider: Lowercase<ConnectionProviderType>) {
  const response = await api.get<ConnectionConfiguration>(`/api/v1/admin/connections/${provider}`);
  return response.data;
}

export async function updateConnectionConfig(provider: Lowercase<ConnectionProviderType>, payload: Record<string, unknown>) {
  const response = await api.put<ConnectionConfiguration>(`/api/v1/admin/connections/${provider}`, payload);
  return response.data;
}

export async function testConnection(provider: Lowercase<ConnectionProviderType>) {
  const response = await api.post<ConnectionTestResponse>(`/api/v1/admin/connections/${provider}/test`);
  return response.data;
}

export async function getDirectoryGroups(params: AdminListParams = {}) {
  const response = await api.get<DirectoryGroup[]>('/api/v1/admin/directory-groups', { params: { limit: 100, ...params } });
  return response.data;
}

export async function importDirectoryGroups(groups: Array<Pick<DirectoryGroup, 'provider_type' | 'external_id' | 'distinguished_name' | 'name' | 'description' | 'member_count'>>) {
  const response = await api.post<DirectoryGroup[]>('/api/v1/admin/directory-groups/import', { groups });
  return response.data;
}

export async function getAuthMappings(params: AdminListParams = {}) {
  const response = await api.get<AuthGroupMapping[]>('/api/v1/admin/auth-mappings', { params: { limit: 100, ...params } });
  return response.data;
}

export async function createAuthMapping(payload: Record<string, unknown>) {
  const response = await api.post<AuthGroupMapping>('/api/v1/admin/auth-mappings', payload);
  return response.data;
}

export async function getConnectionLogs(params: AdminListParams = {}) {
  const response = await api.get<ConnectionEventLog[]>('/api/v1/admin/connection-logs', { params: { limit: 100, ...params } });
  return response.data;
}

export async function createAdminReference<T>(resource: string, payload: Record<string, unknown>) {
  const response = await api.post<T>(`/api/v1/admin/${resource}`, payload);
  return response.data;
}

export async function updateAdminReference<T>(resource: string, id: Uuid, payload: Record<string, unknown>) {
  const response = await api.patch<T>(`/api/v1/admin/${resource}/${id}`, payload);
  return response.data;
}
