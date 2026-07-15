import {
  AppstoreOutlined,
  DashboardOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Avatar, Divider, Dropdown, Layout, Menu, Popover, Select, Tooltip, Typography, type MenuProps } from 'antd';
import type { PropsWithChildren } from 'react';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { Button, StatusBadge } from '../components/design-system';
import { useAuth } from '../context/AuthContext';
import { useAppTheme } from '../context/ThemeContext';

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard', permissions: [] },
  { key: '/applications', icon: <AppstoreOutlined />, label: 'Applications', permissions: ['requests.view'] },
  { key: '/admin', icon: <SafetyCertificateOutlined />, label: 'Администрирование', permissions: ['admin.dashboard.view', 'admin.contractors.view', 'admin.users.view', 'admin.roles.view', 'admin.audit.view', 'admin.system_status.view', 'reference_data.manage'] },
  { key: '/settings', icon: <SettingOutlined />, label: 'Settings', permissions: [] },
];

const devUserSelectorEnabled = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_USER_SELECTOR === 'true';

function initials(name?: string) {
  return (name ?? 'SP')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'SP';
}

export function AppLayout({ children }: PropsWithChildren) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { appName } = useAppTheme();
  const auth = useAuth();
  const visibleMenuItems = menuItems.filter((item) => item.permissions.length === 0 || auth.hasAnyPermission(item.permissions));
  const selectedKey = visibleMenuItems.find((item) => location.pathname === item.key || (item.key !== '/' && location.pathname.startsWith(item.key)))?.key ?? '/';
  const currentUser = auth.currentUser;
  const primaryRole = currentUser?.role_codes[0] ?? 'Нет роли';
  const secondaryIdentity = currentUser?.username ?? currentUser?.email ?? 'Пользователь не выбран';
  const profileItems: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: 'Профиль' },
    { key: 'roles', icon: <SafetyCertificateOutlined />, label: `Роли и права: ${currentUser?.permissions.length ?? 0} permissions` },
    { type: 'divider' },
    ...(devUserSelectorEnabled ? [{ key: 'developer-tools', icon: <ToolOutlined />, label: 'Developer Tools' }] : []),
    { key: 'logout', label: 'Выйти', disabled: true },
  ];
  const developerTools = devUserSelectorEnabled ? (
    <div className="sp-dev-tools-panel">
      <Typography.Text strong>Тестовый пользователь</Typography.Text>
      <Select
        className="sp-dev-tools-select"
        placeholder="Dev user"
        value={currentUser?.id}
        loading={auth.loading}
        onChange={auth.setDevUserId}
        options={auth.devUsers.map((user) => ({ value: user.id, label: `${user.display_name} (${user.username})` }))}
      />
      <Typography.Text type="secondary">Роли и permissions загружаются из backend seed.</Typography.Text>
    </div>
  ) : null;

  return (
    <Layout className="sp-shell">
      <Layout.Sider
        breakpoint="lg"
        collapsedWidth="0"
        collapsed={collapsed}
        onBreakpoint={setCollapsed}
        className="sp-sidebar"
      >
        <div className="sp-brand">
          <span className="sp-brand-mark">SP</span>
          <span className="sp-brand-name">{appName}</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={visibleMenuItems}
          onClick={({ key }) => navigate(key)}
          className="sp-menu"
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header className="sp-header">
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            aria-label="Toggle navigation"
          />
          <div className="sp-header-meta">
            <Typography.Text strong>{appName}</Typography.Text>
            {import.meta.env.DEV ? <StatusBadge label="DEV" tone="processing" /> : null}
            {developerTools ? (
              <Tooltip title="Доступно только в среде разработки для проверки ролей и прав">
                <Popover content={developerTools} trigger="click" placement="bottomRight">
                  <Button icon={<ToolOutlined />}>Dev user</Button>
                </Popover>
              </Tooltip>
            ) : null}
            <Dropdown menu={{ items: profileItems }} trigger={['click']} placement="bottomRight">
              <button type="button" className="sp-profile-button">
                <Avatar className="sp-profile-avatar">{initials(currentUser?.display_name)}</Avatar>
                <span className="sp-profile-copy">
                  <Typography.Text strong>{currentUser?.display_name ?? 'Не авторизован'}</Typography.Text>
                  <Typography.Text type="secondary">{secondaryIdentity}</Typography.Text>
                </span>
                <Divider type="vertical" className="sp-profile-divider" />
                <span className="sp-profile-role">{primaryRole}</span>
              </button>
            </Dropdown>
          </div>
        </Layout.Header>
        <Layout.Content className="sp-content">{children}</Layout.Content>
        <Layout.Footer className="sp-footer">Security Platform</Layout.Footer>
      </Layout>
    </Layout>
  );
}
