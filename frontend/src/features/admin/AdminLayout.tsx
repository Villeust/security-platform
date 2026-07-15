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

const adminItems = [
  { key: '/admin', icon: <DashboardOutlined />, label: 'Панель управления' },
  { key: '/admin/contractors', icon: <BankOutlined />, label: 'Компании' },
  { key: '/admin/users', icon: <UserOutlined />, label: 'Пользователи' },
  { key: '/admin/cities', icon: <EnvironmentOutlined />, label: 'Города' },
  { key: '/admin/facilities', icon: <BuildOutlined />, label: 'Объекты' },
  { key: '/admin/premises', icon: <HomeOutlined />, label: 'Помещения' },
  { key: '/admin/responsibilities', icon: <DeploymentUnitOutlined />, label: 'Зоны ответственности' },
  { key: '/admin/work-types', icon: <ToolOutlined />, label: 'Направления работ' },
  { key: '/admin/roles', icon: <TeamOutlined />, label: 'Роли' },
  { key: '/admin/audit', icon: <AuditOutlined />, label: 'Журнал действий' },
  { key: '/admin/system-status', icon: <SafetyCertificateOutlined />, label: 'Состояние сервисов' },
];

export function AdminLayout({ children }: PropsWithChildren) {
  const location = useLocation();
  const navigate = useNavigate();
  const selectedKey = adminItems.find((item) => location.pathname === item.key || (item.key !== '/admin' && location.pathname.startsWith(item.key)))?.key ?? '/admin';
  return (
    <div className="admin-layout">
      <aside className="admin-nav">
        <Menu mode="inline" selectedKeys={[selectedKey]} items={adminItems} onClick={({ key }) => navigate(key)} />
      </aside>
      <main className="admin-content">{children}</main>
    </div>
  );
}
