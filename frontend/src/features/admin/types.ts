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
  role_ids: Uuid[];
  role_codes: string[];
  contractor_memberships: ContractorMembership[];
  created_at: string;
  updated_at: string;
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
