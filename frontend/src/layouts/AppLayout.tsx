import {
  AppstoreOutlined,
  DashboardOutlined,
  LogoutOutlined,
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

import { PlatformLogo } from '../components/branding';
import { Button, StatusBadge } from '../components/design-system';
import { DEV_USER_SELECTOR_ENABLED, useAuth } from '../context/AuthContext';

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard', permissions: [] },
  { key: '/applications', icon: <AppstoreOutlined />, label: 'Applications', permissions: ['requests.view'] },
  { key: '/admin', icon: <SafetyCertificateOutlined />, label: 'Администрирование', permissions: ['admin.dashboard.view', 'admin.contractors.view', 'admin.users.view', 'admin.roles.view', 'admin.audit.view', 'admin.system_status.view', 'admin.connections.view', 'admin.notifications.view'] },
  { key: '/settings', icon: <SettingOutlined />, label: 'Settings', permissions: [] },
];

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
  const auth = useAuth();
  const visibleMenuItems = menuItems.filter((item) => item.permissions.length === 0 || auth.hasAnyPermission(item.permissions));
  const selectedKey = visibleMenuItems.find((item) => location.pathname === item.key || (item.key !== '/' && location.pathname.startsWith(item.key)))?.key ?? '/';
  const currentUser = auth.currentUser;
  const primaryRole = currentUser?.role_codes[0] ?? 'Без роли';
  const secondaryIdentity = currentUser?.email ?? currentUser?.username ?? 'Пользователь не выбран';

  const profileItems: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: 'Профиль', disabled: true },
    { key: 'roles', icon: <SafetyCertificateOutlined />, label: `Роли и права: ${currentUser?.permissions.length ?? 0}`, disabled: true },
    ...(DEV_USER_SELECTOR_ENABLED ? [{ type: 'divider' as const }, { key: 'developer-tools', icon: <ToolOutlined />, label: 'Developer Tools', disabled: true }] : []),
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: 'Выйти' },
  ];

  const developerTools = DEV_USER_SELECTOR_ENABLED ? (
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
      <Typography.Text type="secondary">Пользователь выбирается из seed-данных; роли и permissions загружаются из backend.</Typography.Text>
    </div>
  ) : null;

  return (
    <Layout className="sp-shell">
      <Layout.Sider breakpoint="lg" collapsedWidth={72} collapsed={collapsed} onBreakpoint={setCollapsed} className={`sp-sidebar ${collapsed ? 'sp-sidebar-collapsed' : ''}`}>
        <div className="sp-brand">
          <PlatformLogo variant={collapsed ? 'compact' : 'header'} className="sp-brand-logo" />
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]} items={visibleMenuItems} onClick={({ key }) => navigate(key)} className="sp-menu" />
      </Layout.Sider>
      <Layout>
        <Layout.Header className="sp-header">
          <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(!collapsed)} aria-label="Toggle navigation" />
          <div className="sp-header-meta">
            <span className="sp-header-brand">
              <PlatformLogo variant="header" className="sp-header-logo" />
            </span>
            {import.meta.env.DEV ? <StatusBadge label="DEV" tone="processing" /> : null}
            {developerTools ? (
              <Tooltip title="Доступно только в среде разработки для проверки ролей и прав">
                <Popover content={developerTools} trigger="click" placement="bottomRight">
                  <Button icon={<ToolOutlined />}>Dev user</Button>
                </Popover>
              </Tooltip>
            ) : null}
            <Dropdown
              menu={{
                items: profileItems,
                onClick: ({ key }) => {
                  if (key === 'logout') {
                    void auth.logout().then(() => navigate('/login', { replace: true }));
                  }
                },
              }}
              trigger={['click']}
              placement="bottomRight"
            >
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
