import type { Uuid as BaseUuid } from '../contractor-requests/types/api';

export type Uuid = BaseUuid;

export type UserType = 'INTERNAL' | 'CONTRACTOR';
export type AuthSource = 'LOCAL' | 'ADFS' | 'LDAP';

export type AdminDashboard = {
  contractors_total: number;
  contractors_active: number;
  users_total: number;
  users_active: number;
  cities_total: number;
  facilities_total: number;
  premises_total: number;
  responsibilities_total: number;
  requests_active: number;
  work_types_total: number;
};

export type SystemStatusItem = {
  status: 'operational' | 'configured' | 'not_configured' | 'planned' | 'degraded' | string;
  description: string;
};

export type SystemStatus = {
  backend: SystemStatusItem;
  database: SystemStatusItem;
  frontend_configured: SystemStatusItem;
  email_configured: SystemStatusItem;
  adfs_configured: SystemStatusItem;
  contractor_portal_status: SystemStatusItem;
};

export type AdminContractor = {
  id: Uuid;
  name: string;
  code: string;
  email: string | null;
  phone: string | null;
  users_count: number;
  responsibilities_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Role = {
  id: Uuid;
  code: string;
  name: string;
  description: string | null;
  users_count: number;
  permissions_count: number;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Permission = {
  id: Uuid;
  code: string;
  name: string;
  description: string | null;
  resource: string;
  action: string;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ContractorMembership = {
  id: Uuid;
  user_id: Uuid;
  contractor_id: Uuid;
  is_primary: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AdminUser = {
  id: Uuid;
  username: string;
  email: string | null;
  display_name: string;
  user_type: UserType;
  auth_source: AuthSource;
  is_active: boolean;
  is_locked: boolean;
  last_login_at: string | null;
  password_changed_at?: string | null;
  must_change_password: boolean;
  failed_login_attempts?: number;
  locked_until?: string | null;
  last_login_ip?: string | null;
  authentication_enabled?: boolean;
  password_expires_at?: string | null;
  password_expired?: boolean;
  password_days_remaining?: number | null;
  password_expiry_warning?: boolean;
  lock_reason?: string | null;
  locked_at?: string | null;
  role_ids: Uuid[];
  role_codes: string[];
  permissions: string[];
  contractor_memberships: ContractorMembership[];
  created_at: string;
  updated_at: string;
};

export type UserCreateResponse = AdminUser & {
  temporary_password: string | null;
};

export type LoginResponse = {
  user: AdminUser;
  must_change_password: boolean;
};

export type AuthProviderStatus = {
  provider: 'LOCAL' | 'LDAP' | 'ADFS';
  configured: boolean;
  enabled: boolean;
  message?: string | null;
};

export type AuditLog = {
  id: Uuid;
  actor_id: Uuid | null;
  actor_type: string;
  action: string;
  entity_type: string;
  entity_id: Uuid | null;
  old_data: Record<string, unknown> | null;
  new_data: Record<string, unknown> | null;
  created_at: string;
  ip_address: string | null;
  user_agent: string | null;
};

export type AdminListParams = {
  search?: string;
  is_active?: boolean;
  skip?: number;
  limit?: number;
  [key: string]: string | number | boolean | undefined;
};

export type AdminNotification = {
  id: Uuid;
  type: string;
  severity: string;
  title: string;
  message: string;
  user_id: Uuid | null;
  details: Record<string, unknown> | null;
  is_read: boolean;
  is_resolved: boolean;
  created_at: string;
  read_at: string | null;
  resolved_at: string | null;
};

export type ConnectionProviderType = 'LDAP' | 'ADFS' | 'SMTP';

export type ConnectionConfiguration = {
  id: Uuid;
  provider_type: ConnectionProviderType;
  name: string;
  is_active: boolean;
  configuration_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  last_tested_at: string | null;
  last_test_status: string | null;
  last_test_message: string | null;
};

export type ConnectionTestResponse = {
  status: string;
  message: string;
  safe_details: Record<string, unknown> | null;
};

export type DirectoryGroup = {
  id: Uuid;
  provider_type: ConnectionProviderType;
  external_id: string;
  distinguished_name: string;
  name: string;
  description: string | null;
  source_configuration_id: Uuid | null;
  member_count: number | null;
  imported_at: string;
  last_synced_at: string | null;
  is_active: boolean;
};

export type AuthGroupMapping = {
  id: Uuid;
  directory_group_id: Uuid;
  role_id: Uuid;
  contractor_id: Uuid | null;
  all_cities: boolean;
  priority: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ConnectionEventLog = {
  id: Uuid;
  provider_type: ConnectionProviderType;
  configuration_id: Uuid | null;
  event_type: string;
  status: string;
  message: string;
  safe_details: Record<string, unknown> | null;
  actor_id: Uuid | null;
  created_at: string;
};

export type AdminReferenceRecord = {
  id: Uuid;
  name?: string;
  code?: string;
  address?: string;
  city_id?: Uuid | null;
  facility_id?: Uuid | null;
  contractor_id?: Uuid | null;
  work_type_id?: Uuid | null;
  number?: string | null;
  category?: string | null;
  owner_name?: string | null;
  owner_email?: string | null;
  owner_phone?: string | null;
  has_access_control?: boolean;
  requires_premise?: boolean;
  priority?: number;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
};
