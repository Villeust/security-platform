import {
  BellOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Button, Card, Empty, Progress, Segmented, Skeleton, Table, Tag, Tooltip, Typography, type TableProps } from 'antd';
import type { ReactNode } from 'react';

export type DashboardTone = 'info' | 'warning' | 'high' | 'critical' | 'success' | 'neutral';

const toneIcon: Record<DashboardTone, ReactNode> = {
  info: <BellOutlined />,
  warning: <ClockCircleOutlined />,
  high: <ExclamationCircleOutlined />,
  critical: <ExclamationCircleOutlined />,
  success: <CheckCircleOutlined />,
  neutral: <BellOutlined />,
};

export type DashboardPageHeaderProps = {
  title: string;
  subtitle: string;
  userName?: string;
  userRole?: string;
  date: string;
  lastRefresh?: string;
  loading?: boolean;
  onRefresh?: () => void;
  children?: ReactNode;
};

export function DashboardPageHeader({ title, subtitle, userName, userRole, date, lastRefresh, loading, onRefresh, children }: DashboardPageHeaderProps) {
  return (
    <section className="ops-page-header">
      <div className="ops-page-header-copy">
        <Typography.Text className="ops-eyebrow">Security Platform</Typography.Text>
        <Typography.Title level={1}>{title}</Typography.Title>
        <Typography.Text type="secondary">{subtitle}</Typography.Text>
        <div className="ops-header-meta">
          <span>Здравствуйте, {userName ?? 'пользователь'}</span>
          <span>{userRole ?? 'Пользователь'}</span>
          <span>{date}</span>
          {lastRefresh ? <span>Обновлено: {lastRefresh}</span> : null}
        </div>
      </div>
      <div className="ops-page-header-actions">
        {children}
        <Button icon={<ReloadOutlined />} loading={loading} onClick={onRefresh}>
          Обновить
        </Button>
      </div>
    </section>
  );
}

export function DashboardSection({ title, description, action, children, className }: { title: string; description?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`ops-section ${className ?? ''}`}>
      <div className="ops-section-header">
        <div>
          <Typography.Title level={3}>{title}</Typography.Title>
          {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function MetricCard({
  icon,
  label,
  value,
  description,
  tone = 'info',
  tooltip,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  value: number | string;
  description: string;
  tone?: DashboardTone;
  tooltip?: string;
  onClick?: () => void;
}) {
  const card = (
    <button type="button" className={`ops-metric ops-tone-${tone}`} onClick={onClick}>
      <span className="ops-metric-icon">{icon}</span>
      <span className="ops-metric-copy">
        <span className="ops-metric-value">{value}</span>
        <span className="ops-metric-label">{label}</span>
        <span className="ops-metric-description">{description}</span>
      </span>
    </button>
  );

  return tooltip ? <Tooltip title={tooltip}>{card}</Tooltip> : card;
}

export function AttentionCard({ label, count, description, severity, onClick }: { label: string; count: number; description: string; severity: DashboardTone; onClick?: () => void }) {
  return (
    <button type="button" className={`ops-attention ops-tone-${severity}`} onClick={onClick}>
      <span className="ops-attention-icon">{toneIcon[severity] ?? toneIcon.info}</span>
      <span>
        <strong>{count}</strong>
        <Typography.Text>{label}</Typography.Text>
        <small>{description}</small>
      </span>
      <RightOutlined />
    </button>
  );
}

export function SectionCard({ title, extra, children, className }: { title?: string; extra?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={`ops-card ${className ?? ''}`} title={title} extra={extra}>
      {children}
    </Card>
  );
}

export function CompactEmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <Empty
      className="ops-empty"
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={
        <span>
          <strong>{title}</strong>
          {description ? <small>{description}</small> : null}
        </span>
      }
    >
      {action}
    </Empty>
  );
}

export function PeriodSelector({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <Segmented
      className="ops-period"
      value={value}
      onChange={(next) => onChange(String(next))}
      options={[
        { label: 'Сегодня', value: 'today' },
        { label: '7 дней', value: '7d' },
        { label: '30 дней', value: '30d' },
        { label: 'Месяц', value: 'month' },
      ]}
    />
  );
}

export function CompactDataTable<T extends object>(props: TableProps<T>) {
  return <Table<T> className="ops-table" size="middle" pagination={false} scroll={{ x: 'max-content' }} sticky {...props} />;
}

export function StatusPill({ label, tone = 'neutral' }: { label: string; tone?: DashboardTone }) {
  const color: Record<DashboardTone, string> = {
    info: 'blue',
    warning: 'gold',
    high: 'orange',
    critical: 'red',
    success: 'green',
    neutral: 'default',
  };
  return (
    <Tag className="ops-pill" color={color[tone]}>
      {label}
    </Tag>
  );
}

export function ChartCard({ items, labelForStatus }: { items: Array<{ status: string; count: number }>; labelForStatus: (status: string) => string }) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  if (total === 0) {
    return <CompactEmptyState title="Данных за выбранный период нет" description="Распределение появится после создания заявок." />;
  }
  return (
    <div className="ops-status-bars">
      {items.map((item) => {
        const percent = Math.round((item.count / total) * 100);
        return (
          <div className="ops-status-bar" key={item.status}>
            <div>
              <Typography.Text strong>{labelForStatus(item.status)}</Typography.Text>
              <Typography.Text type="secondary">{item.count}</Typography.Text>
            </div>
            <Progress percent={percent} showInfo={false} strokeColor="#2089d6" trailColor="#edf3f8" />
          </div>
        );
      })}
    </div>
  );
}

export function ActivityTimeline({ items, renderTime }: { items: Array<{ id: string; title: string; actor: string | null; category: string; created_at: string }>; renderTime: (value: string) => string }) {
  if (items.length === 0) {
    return <CompactEmptyState title="Событий пока нет" description="Последние безопасные события появятся здесь." />;
  }
  return (
    <div className="ops-activity">
      {items.map((item) => (
        <article className="ops-activity-item" key={item.id}>
          <span className="ops-activity-dot" />
          <div>
            <Typography.Text strong>{item.title}</Typography.Text>
            <small>
              {item.actor ?? 'Система'} · {renderTime(item.created_at)} · {item.category}
            </small>
          </div>
        </article>
      ))}
    </div>
  );
}

export function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="ops-skeleton-grid">
      {Array.from({ length: count }).map((_, index) => (
        <Card className="ops-card" key={index}>
          <Skeleton active paragraph={{ rows: 2 }} />
        </Card>
      ))}
    </div>
  );
}
