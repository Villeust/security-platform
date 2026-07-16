import {
  ApiOutlined,
  AuditOutlined,
  BankOutlined,
  BellOutlined,
  BuildOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  DashboardOutlined,
  DeploymentUnitOutlined,
  EnvironmentOutlined,
  FileSearchOutlined,
  GatewayOutlined,
  HomeOutlined,
  NodeIndexOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Select, Typography } from 'antd';
import type { PropsWithChildren, ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

type AdminItem = {
  key: string;
  icon: ReactNode;
  label: string;
  permission: string;
};

const adminGroups: Array<{ title: string; items: AdminItem[] }> = [
  {
    title: 'Обзор',
    items: [
      { key: '/admin', icon: <DashboardOutlined />, label: 'Панель управления', permission: 'admin.dashboard.view' },
    ],
  },
  {
    title: 'Организация',
    items: [
      { key: '/admin/contractors', icon: <BankOutlined />, label: 'Компании', permission: 'admin.contractors.view' },
      { key: '/admin/users', icon: <UserOutlined />, label: 'Пользователи', permission: 'admin.users.view' },
      { key: '/admin/roles', icon: <TeamOutlined />, label: 'Роли', permission: 'admin.roles.view' },
    ],
  },
  {
    title: 'Справочники',
    items: [
      { key: '/admin/cities', icon: <EnvironmentOutlined />, label: 'Города', permission: 'reference_data.manage' },
      { key: '/admin/facilities', icon: <BuildOutlined />, label: 'Объекты', permission: 'reference_data.manage' },
      { key: '/admin/premises', icon: <HomeOutlined />, label: 'Помещения', permission: 'reference_data.manage' },
      { key: '/admin/work-types', icon: <ToolOutlined />, label: 'Направления работ', permission: 'reference_data.manage' },
      { key: '/admin/responsibilities', icon: <DeploymentUnitOutlined />, label: 'Зоны ответственности', permission: 'reference_data.manage' },
    ],
  },
  {
    title: 'Безопасность',
    items: [
      { key: '/admin/notifications', icon: <BellOutlined />, label: 'Уведомления', permission: 'admin.notifications.view' },
      { key: '/admin/audit', icon: <AuditOutlined />, label: 'Журнал действий', permission: 'admin.audit.view' },
    ],
  },
  {
    title: 'Интеграции',
    items: [
      { key: '/admin/connections', icon: <ApiOutlined />, label: 'Подключения', permission: 'admin.connections.view' },
      { key: '/admin/system-status', icon: <SafetyCertificateOutlined />, label: 'Состояние сервисов', permission: 'admin.system_status.view' },
    ],
  },
  {
    title: 'Центр процессов',
    items: [
      { key: '/admin/workflow-center', icon: <DashboardOutlined />, label: 'Обзор', permission: 'workflows.instances.view' },
      { key: '/admin/workflow-center/definitions', icon: <DeploymentUnitOutlined />, label: 'Определения процессов', permission: 'workflows.view' },
      { key: '/admin/workflow-center/versions', icon: <BranchesOutlined />, label: 'Версии процессов', permission: 'workflows.view' },
      { key: '/admin/workflow-center/validation', icon: <CheckCircleOutlined />, label: 'Проверка процессов', permission: 'workflows.view' },
      { key: '/admin/workflow-center/instances', icon: <NodeIndexOutlined />, label: 'Экземпляры процессов', permission: 'workflows.instances.view' },
      { key: '/admin/workflow-center/sla', icon: <GatewayOutlined />, label: 'Центр SLA', permission: 'workflows.sla.view' },
      { key: '/admin/workflow-center/outbox', icon: <ApiOutlined />, label: 'Монитор событий', permission: 'workflows.instances.view' },
      { key: '/admin/workflow-center/audit', icon: <AuditOutlined />, label: 'Аудит процессов', permission: 'workflows.view' },
      { key: '/admin/workflow-center/health', icon: <FileSearchOutlined />, label: 'Состояние платформы', permission: 'workflows.instances.view' },
    ],
  },
];

export function AdminLayout({ children }: PropsWithChildren) {
  const location = useLocation();
  const navigate = useNavigate();
  const auth = useAuth();

  const visibleGroups = adminGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => auth.hasPermission(item.permission)) }))
    .filter((group) => group.items.length > 0);
  const flatItems = visibleGroups.flatMap((group) => group.items);
  const selectedKey = flatItems.find((item) => location.pathname === item.key || (item.key !== '/admin' && location.pathname.startsWith(item.key)))?.key ?? '/admin';
  const selectedItem = flatItems.find((item) => item.key === selectedKey);
  const selectorOptions = visibleGroups.map((group) => ({
    label: group.title,
    options: group.items.map((item) => ({ value: item.key, label: item.label })),
  }));

  return (
    <div className="admin-layout">
      <div className="admin-nav-compact" aria-label="Раздел администрирования">
        <Typography.Text className="admin-nav-compact-label">Раздел</Typography.Text>
        <Select
          value={selectedItem?.key ?? selectedKey}
          options={selectorOptions}
          onChange={(key) => navigate(key)}
          className="admin-nav-select"
          popupMatchSelectWidth={false}
        />
      </div>
      <aside className="admin-nav" aria-label="Навигация администрирования">
        {visibleGroups.map((group) => (
          <div className="admin-nav-group" key={group.title}>
            <Typography.Text className="admin-nav-group-title">{group.title}</Typography.Text>
            {group.items.map((item) => (
              <button
                type="button"
                key={item.key}
                className={`admin-nav-item ${selectedKey === item.key ? 'admin-nav-item-active' : ''}`}
                onClick={() => navigate(item.key)}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        ))}
      </aside>
      <main className="admin-content">{children}</main>
    </div>
  );
}
