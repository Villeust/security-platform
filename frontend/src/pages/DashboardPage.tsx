import { useEffect, useState } from 'react';
import type { ColumnsType } from 'antd/es/table';

import { Card, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../components/design-system';
import { api } from '../services/api';

type BackendStatus = 'loading' | 'online' | 'offline';

type DashboardRow = {
  key: string;
  area: string;
  status: string;
};

const columns: ColumnsType<DashboardRow> = [
  { title: 'Area', dataIndex: 'area', key: 'area' },
  {
    title: 'Status',
    dataIndex: 'status',
    key: 'status',
    render: (value: string) => <StatusBadge label={value} tone={value === 'Ready' ? 'success' : 'processing'} />,
  },
];

const rows: DashboardRow[] = [
  { key: 'applications', area: 'Applications workspace', status: 'Ready' },
  { key: 'settings', area: 'Settings workspace', status: 'Ready' },
];

export function DashboardPage() {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('loading');

  useEffect(() => {
    api
      .get('/api/v1/health')
      .then(() => setBackendStatus('online'))
      .catch(() => setBackendStatus('offline'));
  }, []);

  return (
    <div className="sp-page">
      <PageHeader title="Dashboard" description="Operational overview for Security Platform." />
      <div className="sp-dashboard-grid">
        <Card title="Backend">
          {backendStatus === 'loading' ? <Loader label="Checking backend" /> : null}
          {backendStatus === 'online' ? <StatusBadge label="Backend online" tone="success" /> : null}
          {backendStatus === 'offline' ? <ErrorState title="Backend offline" description="Health endpoint is unavailable." /> : null}
        </Card>
        <Card title="Workspace">
          <StatusBadge label="Frontend ready" tone="success" />
        </Card>
      </div>
      <Section title="Platform areas">
        <Table<DashboardRow> columns={columns} dataSource={rows} />
      </Section>
    </div>
  );
}
