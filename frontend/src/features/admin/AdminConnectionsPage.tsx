import { ApiOutlined, CheckCircleOutlined, ExperimentOutlined, PlusOutlined } from '@ant-design/icons';
import { Alert, Form, Input, InputNumber, Modal, Select, Space, Switch, Tabs, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, Card, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import {
  createAuthMapping,
  getAuthMappings,
  getConnectionConfig,
  getConnectionLogs,
  getDirectoryGroups,
  getRoles,
  importDirectoryGroups,
  testConnection,
  updateConnectionConfig,
} from './services/adminService';
import type { AuthGroupMapping, ConnectionConfiguration, ConnectionEventLog, DirectoryGroup, Role } from './types';

type ConnectionsTab = 'overview' | 'ldap' | 'adfs' | 'smtp' | 'groups' | 'mappings' | 'logs';

type Props = {
  tab: ConnectionsTab;
};

const tabPath: Record<ConnectionsTab, string> = {
  overview: '/admin/connections',
  ldap: '/admin/connections/ldap',
  adfs: '/admin/connections/adfs',
  smtp: '/admin/connections/smtp',
  groups: '/admin/connections/directory-groups',
  mappings: '/admin/connections/auth-mappings',
  logs: '/admin/connections/logs',
};

export function AdminConnectionsPage({ tab }: Props) {
  const navigate = useNavigate();
  const [configs, setConfigs] = useState<Record<'ldap' | 'adfs' | 'smtp', ConnectionConfiguration | null>>({ ldap: null, adfs: null, smtp: null });
  const [groups, setGroups] = useState<DirectoryGroup[]>([]);
  const [mappings, setMappings] = useState<AuthGroupMapping[]>([]);
  const [logs, setLogs] = useState<ConnectionEventLog[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [mappingModalOpen, setMappingModalOpen] = useState(false);
  const [groupForm] = Form.useForm();
  const [mappingForm] = Form.useForm();
  const roleById = useMemo(() => new Map(roles.map((role) => [role.id, role.code])), [roles]);

  const load = () => {
    setLoading(true);
    Promise.all([
      getConnectionConfig('ldap').catch(() => null),
      getConnectionConfig('adfs').catch(() => null),
      getConnectionConfig('smtp').catch(() => null),
      getDirectoryGroups().catch(() => []),
      getAuthMappings().catch(() => []),
      getConnectionLogs().catch(() => []),
      getRoles().catch(() => []),
    ])
      .then(([ldap, adfs, smtp, groupData, mappingData, logData, roleData]) => {
        setConfigs({ ldap, adfs, smtp });
        setGroups(groupData);
        setMappings(mappingData);
        setLogs(logData);
        setRoles(roleData);
      })
      .catch(() => setError('Не удалось загрузить настройки подключений.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const statusCard = (title: string, config: ConnectionConfiguration | null) => (
    <Card title={<span className="sp-card-title"><ApiOutlined />{title}</span>}>
      <StatusBadge label={config?.is_active ? 'configured' : 'not_configured'} tone={config?.is_active ? 'success' : 'warning'} />
      <p className="sp-card-text">{config?.last_test_message ?? 'Подключение не проверялось.'}</p>
      <Typography.Text type="secondary">Последняя проверка: {config?.last_tested_at ? new Date(config.last_tested_at).toLocaleString('ru-RU') : 'нет'}</Typography.Text>
    </Card>
  );

  const configForm = (provider: 'ldap' | 'adfs' | 'smtp') => {
    const config = configs[provider];
    const initialValues = { name: provider.toUpperCase(), ...(config?.configuration_json ?? {}), is_active: config?.is_active ?? false };
    return (
      <Card>
        <Alert type="info" showIcon message="Секреты сохраняются зашифрованно" description="Пароли и client secret не возвращаются из API в открытом виде. Для LDAP/ADFS успешная внешняя проверка будет доступна после подключения реального провайдера." />
        <Form layout="vertical" initialValues={initialValues} onFinish={(values) => updateConnectionConfig(provider, values).then(() => { message.success('Настройки сохранены'); load(); })}>
          <div className="admin-form-grid">
            <Form.Item name="name" label="Название"><Input /></Form.Item>
            <Form.Item name="is_active" label="Активно" valuePropName="checked"><Switch /></Form.Item>
            {provider !== 'adfs' ? <Form.Item name="host" label="Host"><Input /></Form.Item> : <Form.Item name="authority_url" label="Authority URL"><Input /></Form.Item>}
            {provider !== 'adfs' ? <Form.Item name="port" label="Port"><InputNumber className="admin-full-width" min={1} max={65535} /></Form.Item> : <Form.Item name="client_id" label="Client ID"><Input /></Form.Item>}
            {provider === 'ldap' ? <Form.Item name="base_dn" label="Base DN"><Input /></Form.Item> : null}
            {provider === 'ldap' ? <Form.Item name="bind_username" label="Bind username"><Input /></Form.Item> : null}
            {provider === 'ldap' ? <Form.Item name="bind_password" label="Bind password"><Input.Password /></Form.Item> : null}
            {provider === 'adfs' ? <Form.Item name="client_secret" label="Client secret"><Input.Password /></Form.Item> : null}
            {provider === 'smtp' ? <Form.Item name="username" label="Username"><Input /></Form.Item> : null}
            {provider === 'smtp' ? <Form.Item name="password" label="Password"><Input.Password /></Form.Item> : null}
            {provider === 'smtp' ? <Form.Item name="from_email" label="From email"><Input /></Form.Item> : null}
            {provider === 'smtp' ? <Form.Item name="use_starttls" label="STARTTLS" valuePropName="checked"><Switch /></Form.Item> : null}
          </div>
          <Space>
            <Button type="primary" htmlType="submit">Сохранить</Button>
            <Button icon={<ExperimentOutlined />} onClick={() => testConnection(provider).then((result) => message.info(result.message))}>Проверить</Button>
          </Space>
        </Form>
      </Card>
    );
  };

  const groupColumns: ColumnsType<DirectoryGroup> = [
    { title: 'Провайдер', dataIndex: 'provider_type', key: 'provider_type' },
    { title: 'Группа', dataIndex: 'name', key: 'name' },
    { title: 'DN', dataIndex: 'distinguished_name', key: 'distinguished_name' },
    { title: 'Участники', dataIndex: 'member_count', key: 'member_count', render: (value: number | null) => value ?? '—' },
    { title: 'Статус', dataIndex: 'is_active', key: 'is_active', render: (value: boolean) => <StatusBadge label={value ? 'Активна' : 'Отключена'} tone={value ? 'success' : 'default'} /> },
  ];

  const mappingColumns: ColumnsType<AuthGroupMapping> = [
    { title: 'Группа', dataIndex: 'directory_group_id', key: 'directory_group_id', render: (id: string) => groups.find((group) => group.id === id)?.name ?? id },
    { title: 'Роль', dataIndex: 'role_id', key: 'role_id', render: (id: string) => roleById.get(id) ?? id },
    { title: 'Все города', dataIndex: 'all_cities', key: 'all_cities', render: (value: boolean) => value ? 'Да' : 'Нет' },
    { title: 'Приоритет', dataIndex: 'priority', key: 'priority' },
    { title: 'Статус', dataIndex: 'is_active', key: 'is_active', render: (value: boolean) => <StatusBadge label={value ? 'Активно' : 'Отключено'} tone={value ? 'success' : 'default'} /> },
  ];

  const logColumns: ColumnsType<ConnectionEventLog> = [
    { title: 'Дата', dataIndex: 'created_at', key: 'created_at', render: (value: string) => new Date(value).toLocaleString('ru-RU') },
    { title: 'Провайдер', dataIndex: 'provider_type', key: 'provider_type' },
    { title: 'Событие', dataIndex: 'event_type', key: 'event_type' },
    { title: 'Статус', dataIndex: 'status', key: 'status', render: (value: string) => <StatusBadge label={value} tone={value === 'SUCCESS' ? 'success' : value === 'FAILED' ? 'error' : 'warning'} /> },
    { title: 'Сообщение', dataIndex: 'message', key: 'message' },
  ];

  if (loading) return <Loader label="Загрузка подключений" />;
  if (error) return <ErrorState title="Подключения недоступны" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title="Управление подключениями" description="Конфигурации LDAP, ADFS, SMTP, импорт групп и маппинг ролей. Внешние проверки не имитируют успешную интеграцию." />
      <Tabs
        activeKey={tab}
        onChange={(key) => navigate(tabPath[key as ConnectionsTab])}
        items={[
          { key: 'overview', label: 'Обзор', children: <Section><div className="admin-card-grid">{statusCard('LDAP', configs.ldap)}{statusCard('ADFS', configs.adfs)}{statusCard('SMTP', configs.smtp)}</div></Section> },
          { key: 'ldap', label: 'LDAP', children: configForm('ldap') },
          { key: 'adfs', label: 'ADFS', children: configForm('adfs') },
          { key: 'smtp', label: 'SMTP', children: configForm('smtp') },
          { key: 'groups', label: 'Группы', children: <Section actions={<Button icon={<PlusOutlined />} onClick={() => setGroupModalOpen(true)}>Импортировать группу</Button>}><Table rowKey="id" columns={groupColumns} dataSource={groups} pagination={{ pageSize: 10 }} scroll={{ x: 1000 }} /></Section> },
          { key: 'mappings', label: 'Маппинг ролей', children: <Section actions={<Button icon={<PlusOutlined />} onClick={() => setMappingModalOpen(true)}>Добавить mapping</Button>}><Table rowKey="id" columns={mappingColumns} dataSource={mappings} pagination={{ pageSize: 10 }} scroll={{ x: 1000 }} /></Section> },
          { key: 'logs', label: 'Логи', children: <Section><Table rowKey="id" columns={logColumns} dataSource={logs} pagination={{ pageSize: 10 }} scroll={{ x: 1000 }} /></Section> },
        ]}
      />
      <Modal title="Импорт группы" open={groupModalOpen} onCancel={() => setGroupModalOpen(false)} onOk={() => groupForm.validateFields().then((values) => importDirectoryGroups([{ provider_type: 'LDAP', ...values }]).then(() => { message.success('Группа импортирована'); setGroupModalOpen(false); load(); }))} destroyOnHidden>
        <Form form={groupForm} layout="vertical">
          <Form.Item name="external_id" label="External ID" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="name" label="Название" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="distinguished_name" label="Distinguished Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="Описание"><Input /></Form.Item>
          <Form.Item name="member_count" label="Участников"><InputNumber className="admin-full-width" min={0} /></Form.Item>
        </Form>
      </Modal>
      <Modal title="Маппинг группы на роль" open={mappingModalOpen} onCancel={() => setMappingModalOpen(false)} onOk={() => mappingForm.validateFields().then((values) => createAuthMapping(values).then(() => { message.success('Mapping создан'); setMappingModalOpen(false); load(); }))} destroyOnHidden>
        <Form form={mappingForm} layout="vertical" initialValues={{ all_cities: true, is_active: true, priority: 100 }}>
          <Form.Item name="directory_group_id" label="Группа" rules={[{ required: true }]}><Select options={groups.map((group) => ({ value: group.id, label: group.name }))} /></Form.Item>
          <Form.Item name="role_id" label="Роль" rules={[{ required: true }]}><Select options={roles.map((role) => ({ value: role.id, label: role.code }))} /></Form.Item>
          <Form.Item name="all_cities" label="Все города" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item name="priority" label="Приоритет"><InputNumber className="admin-full-width" min={1} /></Form.Item>
          <Form.Item name="is_active" label="Активно" valuePropName="checked"><Switch /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
