import { AppstoreOutlined, InboxOutlined } from '@ant-design/icons';
import { Avatar, Card, Space, Table, Tag, Timeline as AntTimeline, Typography, type TableProps, type TimelineProps } from 'antd';
import type { ReactNode } from 'react';

import { Button } from '../../components/design-system';
import type { AssignmentStatus, RequestStatus } from '../contractor-requests/types/api';
import { assignmentStatusLabel, assignmentTone, priorityLabel, requestStatusLabel, requestTone } from './constants';

type PortalPageProps = {
  title: string;
  description?: string;
  eyebrow?: string;
  actions?: ReactNode;
  children: ReactNode;
};

const tagColor = {
  success: 'success',
  processing: 'processing',
  warning: 'warning',
  error: 'error',
  default: 'default',
} as const;

export function PageHeader({ title, description, eyebrow = 'Портал подрядчика', actions }: Omit<PortalPageProps, 'children'>) {
  return (
    <header className="contractor-page-header">
      <div>
        <Typography.Text className="contractor-eyebrow">{eyebrow}</Typography.Text>
        <Typography.Title level={1}>{title}</Typography.Title>
        {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
      </div>
      {actions ? <div className="contractor-page-actions">{actions}</div> : null}
    </header>
  );
}

export function PortalPage({ title, description, eyebrow, actions, children }: PortalPageProps) {
  return (
    <main className="contractor-page">
      <PageHeader title={title} description={description} eyebrow={eyebrow} actions={actions} />
      {children}
    </main>
  );
}

export function DashboardSection({ title, description, actions, children }: { title: string; description?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="contractor-section">
      <div className="contractor-section-header">
        <div>
          <Typography.Title level={3}>{title}</Typography.Title>
          {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
        </div>
        {actions ? <Space>{actions}</Space> : null}
      </div>
      {children}
    </section>
  );
}

export function SectionCard({ title, description, actions, children, className = '' }: { title?: string; description?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={`contractor-card contractor-section-card ${className}`} title={title ? <div><Typography.Text strong>{title}</Typography.Text>{description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}</div> : undefined} extra={actions}>
      {children}
    </Card>
  );
}

export function StatusBadge({ label, tone = 'default' }: { label: string; tone?: keyof typeof tagColor }) {
  return <Tag className={`contractor-status contractor-status-${tone}`} color={tagColor[tone]}>{label}</Tag>;
}

export function RequestStatusBadge({ status }: { status: RequestStatus }) {
  return <StatusBadge label={requestStatusLabel[status]} tone={requestTone(status)} />;
}

export function AssignmentStatusBadge({ status }: { status: AssignmentStatus }) {
  return <StatusBadge label={assignmentStatusLabel[status]} tone={assignmentTone(status)} />;
}

export function PriorityBadge({ value }: { value?: string | null }) {
  const tone = value === 'CRITICAL' ? 'error' : value === 'HIGH' ? 'warning' : value === 'LOW' ? 'default' : 'processing';
  return <StatusBadge label={value ? priorityLabel[value] ?? value : 'Без приоритета'} tone={tone} />;
}

export function EmptyState({ title, description, actionLabel, onAction, icon }: { title: string; description: string; actionLabel?: string; onAction?: () => void; icon?: ReactNode }) {
  return (
    <div className="contractor-empty compact">
      <div className="contractor-empty-icon">{icon ?? <InboxOutlined />}</div>
      <Typography.Title level={4}>{title}</Typography.Title>
      <Typography.Text type="secondary">{description}</Typography.Text>
      {actionLabel && onAction ? <Button type="primary" onClick={onAction}>{actionLabel}</Button> : null}
    </div>
  );
}

export const ContractorEmptyState = EmptyState;

export function MetricCard({ title, value, description, tone = 'default', icon, onClick }: { title: string; value: number; description: string; tone?: 'default' | 'success' | 'warning' | 'danger' | 'info'; icon?: ReactNode; onClick?: () => void }) {
  return (
    <button type="button" className={`contractor-metric contractor-metric-${tone}`} onClick={onClick}>
      <span className="contractor-metric-icon">{icon ?? <AppstoreOutlined />}</span>
      <span className="contractor-metric-copy">
        <Typography.Text>{title}</Typography.Text>
        <strong>{value}</strong>
        <span>{description}</span>
      </span>
    </button>
  );
}

export function Toolbar({ children }: { children: ReactNode }) {
  return <div className="contractor-toolbar">{children}</div>;
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <SectionCard className="contractor-filter-card"><Toolbar>{children}</Toolbar></SectionCard>;
}

export function DataTable<T extends object>(props: TableProps<T>) {
  return <Table<T> className="contractor-data-table" sticky scroll={{ x: 'max-content', ...props.scroll }} locale={{ emptyText: 'Нет данных', ...props.locale }} {...props} />;
}

export function Timeline(props: TimelineProps) {
  return <AntTimeline className="contractor-timeline" {...props} />;
}

export function ActivityCard({ title, description, icon, actions }: { title: ReactNode; description?: ReactNode; icon?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="contractor-activity-card">
      <span className="contractor-activity-icon">{icon ?? <AppstoreOutlined />}</span>
      <div className="contractor-activity-copy">
        <Typography.Text strong>{title}</Typography.Text>
        {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
      </div>
      {actions ? <div>{actions}</div> : null}
    </div>
  );
}

export function ActionCard({ title, description, icon, onClick }: { title: string; description: string; icon?: ReactNode; onClick?: () => void }) {
  return (
    <button type="button" className="contractor-action-card" onClick={onClick}>
      <span className="contractor-action-icon">{icon ?? <AppstoreOutlined />}</span>
      <span><strong>{title}</strong><small>{description}</small></span>
    </button>
  );
}

export function InfoCard({ label, value, icon }: { label: string; value: ReactNode; icon?: ReactNode }) {
  return <div className="contractor-info-card"><span>{icon}</span><div><Typography.Text type="secondary">{label}</Typography.Text><strong>{value}</strong></div></div>;
}

export function UserCard({ name, meta, role }: { name: string; meta?: string; role?: string }) {
  const initials = name.split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'SP';
  return <div className="contractor-user-card"><Avatar>{initials}</Avatar><div><Typography.Text strong>{name}</Typography.Text>{meta ? <Typography.Text type="secondary">{meta}</Typography.Text> : null}</div>{role ? <StatusBadge label={role} tone="processing" /> : null}</div>;
}
