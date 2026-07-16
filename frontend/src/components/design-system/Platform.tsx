import { RightOutlined } from '@ant-design/icons';
import { Button, Descriptions, Space, Tag, Typography, type DescriptionsProps } from 'antd';
import type { ComponentProps, PropsWithChildren, ReactNode } from 'react';

import { Card } from './Card';
import { EmptyState } from './EmptyState';
import { PageHeader } from './PageHeader';
import { Section } from './Section';
import { Table, type TableProps } from './Table';

export function PlatformPage({ children }: PropsWithChildren) {
  return <div className="sp-page">{children}</div>;
}

export const PlatformPageHeader = PageHeader;
export const PlatformSection = Section;
export const PlatformCard = Card;
export const DataTable = Table;
export const PlatformEmptyState = EmptyState;

export function FilterBar({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <Card className="sp-filter-card">
      <div className="sp-filter-bar">
        <div className="sp-filter-controls">{children}</div>
        {actions ? <div className="sp-filter-actions">{actions}</div> : null}
      </div>
    </Card>
  );
}

export function Toolbar({ children }: PropsWithChildren) {
  return <Space wrap className="sp-toolbar">{children}</Space>;
}

export function ActionCard({ icon, title, description, disabled, onClick }: { icon: ReactNode; title: string; description: string; disabled?: boolean; onClick?: () => void }) {
  return (
    <button type="button" className="sp-action-card" disabled={disabled} onClick={onClick}>
      <span className="sp-action-card-icon">{icon}</span>
      <span className="sp-action-card-copy">
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
      <RightOutlined />
    </button>
  );
}

export function NavigationCard({ icon, title, description, status, disabled, onClick }: { icon: ReactNode; title: string; description: string; status?: string; disabled?: boolean; onClick?: () => void }) {
  return (
    <Card className={`sp-navigation-card ${disabled ? 'sp-navigation-card-disabled' : ''}`}>
      <button type="button" disabled={disabled} onClick={onClick}>
        <span className="sp-navigation-icon">{icon}</span>
        <span className="sp-navigation-copy">
          <Typography.Title level={3}>{title}</Typography.Title>
          <Typography.Text type="secondary">{description}</Typography.Text>
          {status ? <Tag color={disabled ? 'default' : 'blue'}>{status}</Tag> : null}
        </span>
        <RightOutlined />
      </button>
    </Card>
  );
}

export function InfoList({ items }: { items: DescriptionsProps['items'] }) {
  return <Descriptions className="sp-info-list" bordered column={{ xs: 1, sm: 1, md: 2, lg: 2, xl: 3 }} items={items} />;
}

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="sp-loading-grid">
      {Array.from({ length: rows }).map((_, index) => (
        <Card key={index} loading />
      ))}
    </div>
  );
}

export function TableActions({ children }: PropsWithChildren) {
  return <Space wrap size={8}>{children}</Space>;
}

export function PlatformButton(props: ComponentProps<typeof Button>) {
  return <Button {...props} />;
}
