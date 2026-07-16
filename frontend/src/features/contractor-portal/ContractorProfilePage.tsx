import { SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons';
import { Avatar, Card, Descriptions, List, Space, Tag, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, Loader, StatusBadge } from '../../components/design-system';
import { useAuth } from '../../context/AuthContext';
import { authSourceLabel, formatDate, roleLabel } from './constants';
import { PortalPage } from './components';
import { getContractorProfile } from './services';
import type { ContractorMe } from './types';

function initials(name?: string) {
  return (name ?? 'SP').split(' ').filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'SP';
}

export function ContractorProfilePage() {
  const [profile, setProfile] = useState<ContractorMe | null>(null);
  const auth = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    void getContractorProfile().then(setProfile);
  }, []);

  if (!profile) return <Loader label="Загрузка профиля" />;

  const currentUser = auth.currentUser;
  const roles = profile.roles.filter((role) => role.startsWith('CONTRACTOR_'));

  return (
    <PortalPage title="Профиль" description="Данные учётной записи подрядчика и параметры безопасности">
      <Card className="contractor-card">
        <div className="contractor-profile-hero">
          <Avatar className="sp-profile-avatar contractor-profile-avatar" icon={<UserOutlined />}>{initials(profile.display_name)}</Avatar>
          <div>
            <Typography.Title level={3}>{profile.display_name}</Typography.Title>
            <Typography.Text type="secondary">{profile.username}{profile.email ? ` · ${profile.email}` : ''}</Typography.Text>
            <div className="contractor-actions">
              {roles.map((role) => <Tag key={role} color="blue">{roleLabel[role] ?? 'Подрядчик'}</Tag>)}
              <StatusBadge label={currentUser?.is_active ? 'Активна' : 'Отключена'} tone={currentUser?.is_active ? 'success' : 'default'} />
            </div>
          </div>
        </div>
      </Card>

      <Card className="contractor-card" title="Компании">
        <List
          dataSource={profile.contractors}
          renderItem={(company) => (
            <List.Item>
              <List.Item.Meta
                avatar={<SafetyCertificateOutlined />}
                title={<Space><Typography.Text strong>{company.name}</Typography.Text>{company.is_primary ? <Tag color="blue">Основная</Tag> : null}<StatusBadge label="Активна" tone="success" /></Space>}
                description={`${company.code} · ${roles.map((role) => roleLabel[role] ?? 'Подрядчик').join(', ') || 'Подрядчик'}`}
              />
            </List.Item>
          )}
        />
      </Card>

      <Card className="contractor-card" title="Безопасность">
        <Descriptions column={{ xs: 1, md: 2 }}>
          <Descriptions.Item label="Источник авторизации">{authSourceLabel[currentUser?.auth_source ?? 'LOCAL'] ?? 'Локальная учётная запись'}</Descriptions.Item>
          <Descriptions.Item label="Срок действия пароля">{formatDate(currentUser?.password_expires_at)}</Descriptions.Item>
          <Descriptions.Item label="Последний вход">{formatDate(currentUser?.last_login_at, true)}</Descriptions.Item>
          <Descriptions.Item label="Активные сессии">Текущая сессия активна</Descriptions.Item>
        </Descriptions>
        <div className="contractor-actions">
          {currentUser?.auth_source === 'LOCAL' ? <Button onClick={() => navigate('/profile/change-password')}>Сменить пароль</Button> : null}
          <Button>Завершить все другие сессии</Button>
        </div>
      </Card>
    </PortalPage>
  );
}
