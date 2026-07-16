import {
  AppstoreOutlined,
  BellOutlined,
  DashboardOutlined,
  KeyOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Avatar, Badge, Divider, Dropdown, Layout, Menu, Select, Tooltip, Typography, type MenuProps } from 'antd';
import type { PropsWithChildren } from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { PlatformLogo } from '../components/branding';
import { Button, StatusBadge } from '../components/design-system';
import { DEV_USER_SELECTOR_ENABLED, useAuth } from '../context/AuthContext';
import { roleLabel } from '../features/dashboard/constants';

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Центр управления', permissions: [] },
  { key: '/applications', icon: <AppstoreOutlined />, label: 'Модули', permissions: ['requests.view'] },
  { key: '/admin', icon: <SafetyCertificateOutlined />, label: 'Администрирование', permissions: ['admin.dashboard.view', 'admin.contractors.view', 'admin.users.view', 'admin.roles.view', 'admin.audit.view', 'admin.system_status.view', 'admin.connections.view', 'admin.notifications.view'] },
  { key: '/settings', icon: <SettingOutlined />, label: 'Настройки', permissions: [] },
];

const pageTitles = [
  { prefix: '/applications/contractor-requests', title: 'Заявки подрядчикам' },
  { prefix: '/applications', title: 'Модули' },
  { prefix: '/admin', title: 'Администрирование' },
  { prefix: '/settings', title: 'Настройки' },
  { prefix: '/', title: 'Центр управления' },
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
  const [collapsed, setCollapsed] = useState(() => (typeof window === 'undefined' ? false : window.innerWidth <= 1366));
  const location = useLocation();
  const navigate = useNavigate();
  const auth = useAuth();
  const visibleMenuItems = menuItems.filter((item) => item.permissions.length === 0 || auth.hasAnyPermission(item.permissions));
  const selectedKey = visibleMenuItems.find((item) => location.pathname === item.key || (item.key !== '/' && location.pathname.startsWith(item.key)))?.key ?? '/';
  const pageTitle = useMemo(() => pageTitles.find((item) => location.pathname === item.prefix || (item.prefix !== '/' && location.pathname.startsWith(item.prefix)))?.title ?? 'Security Platform', [location.pathname]);
  const currentUser = auth.currentUser;
  const primaryRoleCode = currentUser?.role_codes[0];
  const primaryRole = primaryRoleCode ? roleLabel[primaryRoleCode] ?? primaryRoleCode : 'Без роли';
  const secondaryIdentity = currentUser?.username ?? 'Пользователь не выбран';
  const userEmail = currentUser?.email ?? 'Email не указан';

  const profileItems: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: 'Профиль', disabled: true },
    { key: 'roles', icon: <SafetyCertificateOutlined />, label: `Роли и права: ${primaryRole}`, disabled: true },
    { key: 'change-password', icon: <KeyOutlined />, label: 'Сменить пароль' },
    ...(DEV_USER_SELECTOR_ENABLED ? [{ type: 'divider' as const }, { key: 'developer-tools', icon: <ToolOutlined />, label: 'Инструменты разработчика', disabled: true }] : []),
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: 'Выйти' },
  ];

  const developerTools = DEV_USER_SELECTOR_ENABLED ? (
    <div className="sp-dev-tools-panel">
      <Typography.Text strong>Тестовый пользователь</Typography.Text>
      <Select
        className="sp-dev-tools-select"
        placeholder="Тестовый пользователь"
        value={currentUser?.id}
        loading={auth.loading}
        onChange={auth.setDevUserId}
        options={auth.devUsers.map((user) => ({ value: user.id, label: `${user.display_name} (${user.username})` }))}
      />
      <Typography.Text type="secondary">Пользователь выбирается из seed-данных; роли и permissions загружаются из backend.</Typography.Text>
      <Button
        onClick={() => {
          void auth.resetLocalSession().then(() => navigate('/login', { replace: true }));
        }}
      >
        Сбросить локальную сессию
      </Button>
    </div>
  ) : null;

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth <= 1366) {
        setCollapsed(true);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <Layout className="sp-shell">
      <Layout.Sider breakpoint="lg" collapsedWidth={72} collapsed={collapsed} onBreakpoint={setCollapsed} className={`sp-sidebar ${collapsed ? 'sp-sidebar-collapsed' : ''}`}>
        <div className="sp-brand" aria-label="Security Platform">
          <PlatformLogo variant={collapsed ? 'compact' : 'header'} className="sp-brand-logo" />
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]} items={visibleMenuItems} onClick={({ key }) => navigate(key)} className="sp-menu" />
        <div className="sp-sidebar-footer">
          <Badge status="success" text={collapsed ? '' : 'Подключено'} />
          {!collapsed ? (
            <>
              <Typography.Text>Security Platform</Typography.Text>
              <Typography.Text type="secondary">Версия 0.1.0</Typography.Text>
            </>
          ) : null}
        </div>
      </Layout.Sider>
      <Layout>
        <Layout.Header className="sp-header">
          <div className="sp-header-left">
            <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(!collapsed)} aria-label="Переключить навигацию" />
            <Typography.Title level={4} className="sp-header-title">{pageTitle}</Typography.Title>
          </div>
          <div className="sp-header-meta">
            <Tooltip title="Уведомления">
              <Button type="text" aria-label="Уведомления" icon={<Badge dot><BellOutlined /></Badge>} />
            </Tooltip>
            {import.meta.env.DEV ? (
              <Tooltip title="Среда разработки">
                <span className="sp-dev-badge"><StatusBadge label="DEV" tone="processing" /></span>
              </Tooltip>
            ) : null}
            <Dropdown
              menu={{
                items: profileItems,
                onClick: ({ key }) => {
                  if (key === 'logout') {
                    void auth.logout().then(() => navigate('/login', { replace: true }));
                  }
                  if (key === 'change-password') {
                    navigate('/profile/change-password');
                  }
                },
              }}
              popupRender={(menu) => (
                <div className="sp-profile-dropdown">
                  <div className="sp-profile-dropdown-summary">
                    <Avatar className="sp-profile-avatar">{initials(currentUser?.display_name)}</Avatar>
                    <div>
                      <Typography.Text strong>{currentUser?.display_name ?? 'Не авторизован'}</Typography.Text>
                      <Typography.Text type="secondary">{secondaryIdentity}</Typography.Text>
                      <Typography.Text type="secondary">{userEmail}</Typography.Text>
                      <Typography.Text className="sp-profile-dropdown-role">{primaryRole}</Typography.Text>
                    </div>
                  </div>
                  {menu}
                  {developerTools ? (
                    <div className="sp-profile-dropdown-dev">
                      {developerTools}
                    </div>
                  ) : null}
                </div>
              )}
              trigger={['click']}
              placement="bottomRight"
            >
              <button type="button" className="sp-profile-button" aria-label="Меню пользователя" title={`${currentUser?.display_name ?? 'Пользователь'} · ${primaryRole}`}>
                <Avatar className="sp-profile-avatar sp-profile-avatar-compact">{initials(currentUser?.display_name)}</Avatar>
                <span className="sp-profile-copy">
                  <Typography.Text strong>{currentUser?.display_name ?? 'Не авторизован'}</Typography.Text>
                  <Typography.Text type="secondary">{primaryRole}</Typography.Text>
                </span>
                <Divider type="vertical" className="sp-profile-divider" />
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
