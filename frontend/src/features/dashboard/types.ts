export type DashboardPeriodKey = 'today' | '7d' | '30d' | 'month';

export type DashboardMetric = {
  key: string;
  label: string;
  value: number;
  description: string;
};

export type DashboardAttentionItem = {
  key: string;
  label: string;
  count: number;
  description: string;
  severity: 'informational' | 'warning' | 'high' | 'critical' | string;
  target: string;
};

export type DashboardRequestItem = {
  id: string;
  request_number: string | null;
  title: string;
  facility: string | null;
  city: string | null;
  work_types: string[];
  contractor: string | null;
  status: string;
  priority: string | null;
  desired_completion_date: string | null;
  updated_at: string;
};

export type DashboardContractorSummaryItem = {
  contractor_id: string;
  company: string;
  active_assignments: number;
  in_progress: number;
  awaiting_acceptance: number;
  overdue: number;
  completed: number;
  average_completion_hours: number | null;
  status: string;
};

export type DashboardDeadlineItem = {
  request_id: string;
  request_number: string | null;
  title: string;
  facility: string | null;
  contractor: string | null;
  desired_completion_date: string;
  severity: string;
};

export type DashboardActivityItem = {
  id: string;
  title: string;
  category: string;
  actor: string | null;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
};

export type DashboardNotificationItem = {
  id: string;
  title: string;
  message: string;
  severity: string;
  created_at: string;
};

export type DashboardServiceStatusItem = {
  key: string;
  label: string;
  status: string;
  description: string;
  last_check: string | null;
  target: string | null;
};

export type DashboardResponse = {
  generated_at: string;
  period: {
    key: DashboardPeriodKey;
    date_from: string;
    date_to: string;
  };
  attention: DashboardAttentionItem[];
  metrics: DashboardMetric[];
  request_status_distribution: Array<{ status: string; count: number }>;
  request_groups: Record<string, DashboardRequestItem[]>;
  upcoming_deadlines: DashboardDeadlineItem[];
  contractor_summary: DashboardContractorSummaryItem[];
  recent_activity: DashboardActivityItem[];
  notifications: {
    unread_count: number;
    items: DashboardNotificationItem[];
  };
  system_status: DashboardServiceStatusItem[];
};
