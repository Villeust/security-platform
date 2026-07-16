import { BellOutlined, DashboardOutlined, FileTextOutlined, LogoutOutlined, MenuFoldOutlined, MenuUnfoldOutlined, ProfileOutlined, UnorderedListOutlined, UserOutlined } from '@ant-design/icons';
import { Avatar, Badge, Dropdown, Layout, Menu, Tooltip, Typography, type MenuProps } from 'antd';
import type { PropsWithChildren } from 'react';
import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { PlatformLogo } from '../../components/branding';
import { Button, StatusBadge } from '../../components/design-system';
import { useAuth } from '../../context/AuthContext';
import { roleLabel } from './constants';

const menuItems = [
  { key: '/contractor', icon: <DashboardOutlined />, label: 'Главная' },
  { key: '/contractor/requests', icon: <FileTextOutlined />, label: 'Заявки' },
  { key: '/contractor/tasks', icon: <UnorderedListOutlined />, label: 'Задачи' },
  { key: '/contractor/notifications', icon: <BellOutlined />, label: 'Уведомления' },
  { key: '/contractor/profile', icon: <ProfileOutlined />, label: 'Профиль' },
];

const pageTitles: Record<string, string> = {
  '/contractor': 'Главная',
  '/contractor/requests': 'Заявки',
  '/contractor/tasks': 'Задачи',
  '/contractor/notifications': 'Уведомления',
  '/contractor/profile': 'Профиль',
};

function initials(name?: string) {
  return (name ?? 'SP').split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'SP';
}

export function ContractorLayout({ children }: PropsWithChildren) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const auth = useAuth();

  const selectedKey = menuItems.find((item) => location.pathname === item.key || (item.key !== '/contractor' && location.pathname.startsWith(item.key)))?.key ?? '/contractor';
  const pageTitle = pageTitles[selectedKey] ?? 'Портал подрядчика';
  const primaryCompany = auth.currentUser?.contractor_memberships.find((item) => item.is_primary) ?? auth.currentUser?.contractor_memberships[0];
  const primaryRole = useMemo(() => auth.currentUser?.role_codes.find((code) => code.startsWith('CONTRACTOR_')), [auth.currentUser?.role_codes]);
  const role = primaryRole ? roleLabel[primaryRole] ?? 'Подрядчик' : 'Подрядчик';

  const profileItems: MenuProps['items'] = [
    { key: 'profile', icon: <ProfileOutlined />, label: 'Профиль' },
    { key: 'change-password', icon: <UserOutlined />, label: 'Сменить пароль' },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: 'Выйти' },
  ];

  const renderedMenu = menuItems.map((item) => ({
    ...item,
    label: collapsed ? <Tooltip title={item.label} placement="right"><span>{item.label}</span></Tooltip> : item.label,
  }));

  return (
    <Layout className="sp-shell contractor-shell">
      <Layout.Sider breakpoint="lg" collapsedWidth={72} collapsed={collapsed} onBreakpoint={setCollapsed} className={`contractor-sidebar ${collapsed ? 'sp-sidebar-collapsed' : ''}`}>
        <div className="contractor-brand">
          <PlatformLogo variant={collapsed ? 'compact' : 'header'} className="sp-brand-logo" />
          {!collapsed ? <Typography.Text>Портал подрядчика</Typography.Text> : null}
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]} items={renderedMenu} onClick={({ key }) => navigate(key)} className="contractor-menu" />
        <div className="contractor-sidebar-footer">
          {!collapsed ? (
            <>
              <Typography.Text>Текущая организация</Typography.Text>
              <strong>{primaryCompany ? 'Назначена' : 'Не назначена'}</strong>
              <StatusBadge label="Подключено" tone="success" />
              <Typography.Text>Security Platform · v1.0</Typography.Text>
            </>
          ) : (
            <span>SP</span>
          )}
        </div>
      </Layout.Sider>
      <Layout>
        <Layout.Header className="contractor-header">
          <div className="contractor-header-left">
            <PlatformLogo variant="compact" className="contractor-header-logo" />
            <Button type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={() => setCollapsed(!collapsed)} aria-label="Свернуть навигацию" />
            <Typography.Title level={4}>{pageTitle}</Typography.Title>
          </div>
          <div className="contractor-header-meta">
            <Tooltip title="Уведомления">
              <Badge count={0} size="small">
                <Button icon={<BellOutlined />} onClick={() => navigate('/contractor/notifications')} aria-label="Уведомления" />
              </Badge>
            </Tooltip>
            <Dropdown
              menu={{
                items: profileItems,
                onClick: ({ key }) => {
                  if (key === 'profile') navigate('/contractor/profile');
                  if (key === 'change-password') navigate('/profile/change-password');
                  if (key === 'logout') void auth.logout().then(() => navigate('/login', { replace: true }));
                },
              }}
              trigger={['click']}
              placement="bottomRight"
            >
              <button type="button" className="contractor-avatar-button" aria-label={`Профиль: ${role}`}>
                <Avatar className="sp-profile-avatar" icon={<UserOutlined />}>{initials(auth.currentUser?.display_name)}</Avatar>
              </button>
            </Dropdown>
          </div>
        </Layout.Header>
        <Layout.Content className="contractor-content">{children}</Layout.Content>
      </Layout>
    </Layout>
  );
}
