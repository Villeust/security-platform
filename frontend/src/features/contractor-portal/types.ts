import type { ContractorRequest, RequestAssignment, Uuid } from '../contractor-requests/types/api';

export type ContractorCompany = {
  id: Uuid;
  name: string;
  code: string;
  is_primary: boolean;
};

export type ContractorMe = {
  user_id: Uuid;
  username: string;
  display_name: string;
  email: string | null;
  roles: string[];
  permissions: string[];
  primary_contractor_id: Uuid | null;
  contractors: ContractorCompany[];
};

export type ContractorDashboard = {
  active_requests: number;
  assigned_tasks: number;
  in_progress_tasks: number;
  completed_tasks: number;
  latest_requests: ContractorRequest[];
};

export type ContractorNotification = {
  id: string;
  title: string;
  message: string;
  created_at: string | null;
};

export type ContractorRequestFilters = {
  status?: string;
  assignment_status?: string;
  search?: string;
  skip?: number;
  limit?: number;
};

export type ContractorTask = RequestAssignment;
