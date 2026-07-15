export type Uuid = string;

export type RequestStatus = 'NEW' | 'ASSIGNED';
export type AssignmentStatus = 'ASSIGNED' | 'ACCEPTED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export type City = {
  id: Uuid;
  name: string;
  code: string;
  is_active: boolean;
};

export type Facility = {
  id: Uuid;
  city_id: Uuid;
  name: string;
  address: string;
  code: string;
  is_active: boolean;
};

export type Premise = {
  id: Uuid;
  facility_id: Uuid;
  name: string;
  number: string | null;
  category: string | null;
  owner_name: string | null;
  owner_email: string | null;
  owner_phone: string | null;
  has_access_control: boolean;
  is_active: boolean;
};

export type WorkType = {
  id: Uuid;
  name: string;
  code: string;
  requires_premise: boolean;
  is_active: boolean;
};

export type Contractor = {
  id: Uuid;
  name: string;
  code: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
};

export type RequestAssignment = {
  id: Uuid;
  contractor_id: Uuid;
  work_type_id: Uuid;
  status: AssignmentStatus;
  assigned_at: string;
  accepted_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ContractorRequest = {
  id: Uuid;
  request_number: string | null;
  city_id: Uuid;
  facility_id: Uuid;
  premise_id: Uuid | null;
  title: string;
  description: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  status: RequestStatus;
  work_type_ids: Uuid[];
  assignments: RequestAssignment[];
  unassigned_work_type_ids: Uuid[];
  created_at: string;
  updated_at: string;
};

export type CreateContractorRequestPayload = {
  city_id: Uuid;
  facility_id: Uuid;
  premise_id?: Uuid | null;
  title: string;
  description?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  work_type_ids: Uuid[];
};

export type RequestFormValues = CreateContractorRequestPayload & {
  priority?: string;
  desired_completion_date?: string;
};
