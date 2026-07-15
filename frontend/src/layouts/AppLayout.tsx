import {
  AppstoreOutlined,
  DashboardOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { Layout, Menu, Typography } from 'antd';
import type { PropsWithChildren } from 'react';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { Button, StatusBadge } from '../components/design-system';
import { useAppTheme } from '../context/ThemeContext';

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/applications', icon: <AppstoreOutlined />, label: 'Applications' },
  { key: '/settings', icon: <SettingOutlined />, label: 'Settings' },
];

export function AppLayout({ children }: PropsWithChildren) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { appName } = useAppTheme();

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
          selectedKeys={[location.pathname]}
          items={menuItems}
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
            <StatusBadge label="Dev" tone="processing" />
          </div>
        </Layout.Header>
        <Layout.Content className="sp-content">{children}</Layout.Content>
        <Layout.Footer className="sp-footer">Security Platform</Layout.Footer>
      </Layout>
    </Layout>
  );
}
