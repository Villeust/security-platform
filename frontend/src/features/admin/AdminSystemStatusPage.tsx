import { ReloadOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';

import { Button, Card, ErrorState, Loader, PageHeader, Section, StatusBadge } from '../../components/design-system';
import { getSystemStatus } from './services/adminService';
import type { SystemStatus } from './types';

const serviceLabels: Record<keyof SystemStatus, string> = {
  backend: 'Backend API',
  database: 'Database',
  frontend_configured: 'Frontend',
  email_configured: 'Email',
  adfs_configured: 'ADFS',
  contractor_portal_status: 'Contractor Portal',
};

function statusTone(status: string) {
  if (status === 'operational' || status === 'configured') return 'success';
  if (status === 'planned' || status === 'not_configured') return 'warning';
  return 'error';
}

export function AdminSystemStatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    getSystemStatus()
      .then((data) => {
        setStatus(data);
        setLoadedAt(new Date());
      })
      .catch(() => setError('Не удалось загрузить состояние сервисов.'));
  };

  useEffect(load, []);

  if (error) return <ErrorState title="Состояние сервисов недоступно" description={error} />;
  if (!status) return <Loader label="Загрузка состояния сервисов" />;

  return (
    <div className="sp-page">
      <PageHeader title="Состояние сервисов" description="Локальная конфигурационная проверка без внешних сетевых запросов." actions={<Button icon={<ReloadOutlined />} onClick={load}>Обновить</Button>} />
      <Section title={loadedAt ? `Обновлено: ${loadedAt.toLocaleString('ru-RU')}` : undefined}>
        <div className="admin-card-grid">
          {Object.entries(status).map(([key, item]) => (
            <Card key={key} title={serviceLabels[key as keyof SystemStatus]}>
              <StatusBadge label={item.status} tone={statusTone(item.status)} />
              <p className="sp-card-text">{item.description}</p>
            </Card>
          ))}
        </div>
      </Section>
    </div>
  );
}
