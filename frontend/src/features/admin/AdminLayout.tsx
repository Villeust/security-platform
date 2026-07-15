import {
  AuditOutlined,
  BankOutlined,
  BuildOutlined,
  DashboardOutlined,
  DeploymentUnitOutlined,
  EnvironmentOutlined,
  HomeOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Menu } from 'antd';
import type { PropsWithChildren } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

const adminItems = [
  { key: '/admin', icon: <DashboardOutlined />, label: 'Панель управления', permission: 'admin.dashboard.view' },
  { key: '/admin/contractors', icon: <BankOutlined />, label: 'Компании', permission: 'admin.contractors.view' },
  { key: '/admin/users', icon: <UserOutlined />, label: 'Пользователи', permission: 'admin.users.view' },
  { key: '/admin/cities', icon: <EnvironmentOutlined />, label: 'Города', permission: 'reference_data.manage' },
  { key: '/admin/facilities', icon: <BuildOutlined />, label: 'Объекты', permission: 'reference_data.manage' },
  { key: '/admin/premises', icon: <HomeOutlined />, label: 'Помещения', permission: 'reference_data.manage' },
  { key: '/admin/responsibilities', icon: <DeploymentUnitOutlined />, label: 'Зоны ответственности', permission: 'reference_data.manage' },
  { key: '/admin/work-types', icon: <ToolOutlined />, label: 'Направления работ', permission: 'reference_data.manage' },
  { key: '/admin/roles', icon: <TeamOutlined />, label: 'Роли', permission: 'admin.roles.view' },
  { key: '/admin/audit', icon: <AuditOutlined />, label: 'Журнал действий', permission: 'admin.audit.view' },
  { key: '/admin/system-status', icon: <SafetyCertificateOutlined />, label: 'Состояние сервисов', permission: 'admin.system_status.view' },
];

export function AdminLayout({ children }: PropsWithChildren) {
  const location = useLocation();
  const navigate = useNavigate();
  const auth = useAuth();
  const visibleItems = adminItems.filter((item) => auth.hasPermission(item.permission));
  const selectedKey = visibleItems.find((item) => location.pathname === item.key || (item.key !== '/admin' && location.pathname.startsWith(item.key)))?.key ?? '/admin';
  return (
    <div className="admin-layout">
      <aside className="admin-nav">
        <Menu mode="inline" selectedKeys={[selectedKey]} items={visibleItems} onClick={({ key }) => navigate(key)} />
      </aside>
      <main className="admin-content">{children}</main>
    </div>
  );
}
