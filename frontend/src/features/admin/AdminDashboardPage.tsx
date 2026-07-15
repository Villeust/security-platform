import { BankOutlined, BuildOutlined, DeploymentUnitOutlined, PlusOutlined, UserOutlined } from '@ant-design/icons';
import { Space } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, Card, ErrorState, Loader, PageHeader, Section, StatusBadge } from '../../components/design-system';
import { getAdminDashboard, getSystemStatus } from './services/adminService';
import type { AdminDashboard, SystemStatus } from './types';

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState<AdminDashboard | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getAdminDashboard(), getSystemStatus()])
      .then(([dashboardData, statusData]) => {
        setDashboard(dashboardData);
        setSystemStatus(statusData);
      })
      .catch(() => setError('Не удалось загрузить административную панель.'));
  }, []);

  if (error) return <ErrorState title="Администрирование недоступно" description={error} />;
  if (!dashboard || !systemStatus) return <Loader label="Загрузка администрирования" />;

  const cards = [
    ['Компании', dashboard.contractors_total, `${dashboard.contractors_active} активных`, '/admin/contractors', <BankOutlined />],
    ['Пользователи', dashboard.users_total, `${dashboard.users_active} активных`, '/admin/users', <UserOutlined />],
    ['Объекты', dashboard.facilities_total, 'Всего объектов', '/admin/facilities', <BuildOutlined />],
    ['Помещения', dashboard.premises_total, 'Всего помещений', '/admin/premises', <BuildOutlined />],
    ['Зоны ответственности', dashboard.responsibilities_total, 'Всего зон', '/admin/responsibilities', <DeploymentUnitOutlined />],
    ['Заявки', dashboard.requests_active, 'Активные заявки', '/applications/contractor-requests', <DeploymentUnitOutlined />],
  ] as const;

  return (
    <div className="sp-page">
      <PageHeader title="Администрирование" description="Центр управления справочниками, пользователями, ролями и аудитом Security Platform." />
      <Section title="Показатели">
        <div className="admin-card-grid">
          {cards.map(([title, value, description, path, icon]) => (
            <Card key={title} title={<span className="sp-card-title">{icon}{title}</span>}>
              <h2 className="admin-metric">{value}</h2>
              <p className="sp-card-text">{description}</p>
              <Button onClick={() => navigate(path)}>Открыть</Button>
            </Card>
          ))}
        </div>
      </Section>
      <Section title="Быстрые действия">
        <Space wrap>
          <Button icon={<PlusOutlined />} onClick={() => navigate('/admin/contractors')}>Добавить компанию</Button>
          <Button icon={<PlusOutlined />} onClick={() => navigate('/admin/users')}>Добавить пользователя</Button>
          <Button icon={<PlusOutlined />} onClick={() => navigate('/admin/facilities')}>Добавить объект</Button>
          <Button icon={<PlusOutlined />} onClick={() => navigate('/admin/responsibilities')}>Добавить зону ответственности</Button>
        </Space>
      </Section>
      <Section title="Состояние сервисов">
        <div className="admin-card-grid">
          {Object.entries(systemStatus).map(([key, item]) => (
            <Card key={key} title={key}>
              <StatusBadge label={item.status} tone={item.status === 'operational' || item.status === 'configured' ? 'success' : item.status === 'planned' ? 'warning' : 'error'} />
              <p className="sp-card-text">{item.description}</p>
            </Card>
          ))}
        </div>
      </Section>
    </div>
  );
}
