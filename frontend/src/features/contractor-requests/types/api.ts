export type Uuid = string;

export type RequestStatus = 'DRAFT' | 'NEW' | 'PARTIALLY_ASSIGNED' | 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CLOSED' | 'CANCELLED';
export type AssignmentStatus = 'ASSIGNED' | 'ACCEPTED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
export type RequestHistoryEventType =
  | 'CREATED'
  | 'UPDATED'
  | 'PUBLISHED'
  | 'STATUS_CHANGED'
  | 'ASSIGNMENT_CREATED'
  | 'ASSIGNMENT_ACCEPTED'
  | 'ASSIGNMENT_STATUS_CHANGED'
  | 'REOPENED'
  | 'CLOSED'
  | 'CANCELLED'
  | 'COMMENT_ADDED'
  | 'COMMENT_UPDATED'
  | 'COMMENT_DELETED'
  | 'ATTACHMENT_ADDED'
  | 'ATTACHMENT_DELETED'
  | 'WORK_RESULT_ADDED';
export type RequestHistoryActorType = 'SYSTEM' | 'INTERNAL_USER' | 'CONTRACTOR_USER';
export type RequestVisibility = 'SHARED' | 'INTERNAL';
export type RequestAttachmentCategory = 'REQUEST_FILE' | 'WORK_RESULT' | 'ACT' | 'PHOTO' | 'DOCUMENT' | 'OTHER';

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
  city_id: Uuid | null;
  facility_id: Uuid | null;
  premise_id: Uuid | null;
  title: string;
  description: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  priority: string | null;
  desired_completion_date: string | null;
  completed_at: string | null;
  closed_at: string | null;
  status: RequestStatus;
  work_type_ids: Uuid[];
  assignments: RequestAssignment[];
  unassigned_work_type_ids: Uuid[];
  created_at: string;
  updated_at: string;
};

export type CreateContractorRequestPayload = {
  city_id?: Uuid | null;
  facility_id?: Uuid | null;
  premise_id?: Uuid | null;
  title: string;
  description?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  priority?: string | null;
  desired_completion_date?: string | null;
  work_type_ids: Uuid[];
  save_as_draft?: boolean;
};

export type RequestFormValues = CreateContractorRequestPayload & {
  priority?: string;
  desired_completion_date?: string;
};

export type RequestHistoryItem = {
  id: Uuid;
  event_type: RequestHistoryEventType;
  old_status: RequestStatus | null;
  new_status: RequestStatus | null;
  changed_fields: Record<string, { old: unknown; new: unknown }> | null;
  comment: string | null;
  created_at: string;
  actor_type: RequestHistoryActorType;
  actor_id: Uuid | null;
};

export type RequestListParams = {
  search?: string;
  status?: RequestStatus;
  priority?: string;
  city_id?: Uuid;
  facility_id?: Uuid;
  work_type_id?: Uuid;
  contractor_id?: Uuid;
  created_from?: string;
  created_to?: string;
  due_from?: string;
  due_to?: string;
  skip?: number;
  limit?: number;
  sort_by?: 'created_at' | 'updated_at' | 'number' | 'status' | 'priority' | 'desired_completion_date';
  sort_order?: 'asc' | 'desc';
};

export type RequestComment = {
  id: Uuid;
  request_id: Uuid;
  author_type: RequestHistoryActorType;
  author_id: Uuid | null;
  contractor_id: Uuid | null;
  visibility: RequestVisibility;
  body: string;
  created_at: string;
  updated_at: string;
  is_edited: boolean;
  is_deleted: boolean;
};

export type RequestAttachment = {
  id: Uuid;
  request_id: Uuid;
  assignment_id: Uuid | null;
  comment_id: Uuid | null;
  uploaded_by_type: RequestHistoryActorType;
  uploaded_by_id: Uuid | null;
  contractor_id: Uuid | null;
  category: RequestAttachmentCategory;
  visibility: RequestVisibility;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum_sha256: string;
  created_at: string;
  is_deleted: boolean;
};
