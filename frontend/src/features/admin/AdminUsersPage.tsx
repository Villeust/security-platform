import { EditOutlined, PlusOutlined, PoweroffOutlined } from '@ant-design/icons';
import { Form, Input, Modal, Popconfirm, Select, Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';

import { Button, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import {
  createUser,
  getContractors,
  getRoles,
  getUsers,
  setUserActive,
  setUserContractors,
  setUserRoles,
  updateUser,
} from './services/adminService';
import type { AdminContractor, AdminUser, AuthSource, Role, UserType, Uuid } from './types';

type UserFormValues = {
  username: string;
  display_name: string;
  email?: string;
  user_type: UserType;
  auth_source: AuthSource;
  role_ids: Uuid[];
  contractor_ids: Uuid[];
  is_active: boolean;
};

export function AdminUsersPage() {
  const [form] = Form.useForm<UserFormValues>();
  const [items, setItems] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [contractors, setContractors] = useState<AdminContractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string | boolean | undefined>>({});
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const contractorNameById = useMemo(() => new Map(contractors.map((item) => [item.id, item.name])), [contractors]);

  const load = () => {
    setLoading(true);
    Promise.all([getUsers(filters), getRoles(), getContractors()])
      .then(([usersData, rolesData, contractorsData]) => {
        setItems(usersData);
        setRoles(rolesData);
        setContractors(contractorsData);
      })
      .catch(() => setError('Не удалось загрузить пользователей.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [filters]);

  const openModal = (item?: AdminUser) => {
    setEditing(item ?? null);
    form.setFieldsValue(
      item
        ? {
            username: item.username,
            display_name: item.display_name,
            email: item.email ?? undefined,
            user_type: item.user_type,
            auth_source: item.auth_source,
            is_active: item.is_active,
            role_ids: item.role_ids,
            contractor_ids: item.contractor_memberships.map((membership) => membership.contractor_id),
          }
        : { user_type: 'INTERNAL', auth_source: 'LOCAL', role_ids: [], contractor_ids: [], is_active: true },
    );
    setModalOpen(true);
  };

  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        await updateUser(editing.id, {
          username: values.username,
          display_name: values.display_name,
          email: values.email || null,
          user_type: values.user_type,
          auth_source: values.auth_source,
          is_active: values.is_active,
        });
        await setUserRoles(editing.id, values.role_ids);
        await setUserContractors(editing.id, values.contractor_ids);
        message.success('Пользователь обновлен');
      } else {
        await createUser({
          username: values.username,
          display_name: values.display_name,
          email: values.email || null,
          user_type: values.user_type,
          auth_source: values.auth_source,
          is_active: values.is_active,
          role_ids: values.role_ids,
          contractor_memberships: values.contractor_ids.map((contractor_id, index) => ({ contractor_id, is_primary: index === 0, is_active: true })),
        });
        message.success('Пользователь создан');
      }
      setModalOpen(false);
      load();
    } catch {
      message.error('Не удалось сохранить пользователя');
    } finally {
      setSaving(false);
    }
  };

  const columns: ColumnsType<AdminUser> = [
    { title: 'Статус', dataIndex: 'is_active', key: 'is_active', render: (value: boolean) => <StatusBadge label={value ? 'Активен' : 'Отключен'} tone={value ? 'success' : 'default'} /> },
    { title: 'Username', dataIndex: 'username', key: 'username' },
    { title: 'Имя', dataIndex: 'display_name', key: 'display_name' },
    { title: 'Email', dataIndex: 'email', key: 'email', render: (value: string | null) => value ?? '—' },
    { title: 'Тип', dataIndex: 'user_type', key: 'user_type' },
    { title: 'Источник', dataIndex: 'auth_source', key: 'auth_source' },
    {
      title: 'Компания',
      key: 'contractors',
      render: (_, item) => item.contractor_memberships.map((membership) => contractorNameById.get(membership.contractor_id) ?? membership.contractor_id).join(', ') || '—',
    },
    { title: 'Роли', dataIndex: 'role_codes', key: 'role_codes', render: (value: string[]) => value.join(', ') || '—' },
    { title: 'Последняя активность', dataIndex: 'last_login_at', key: 'last_login_at', render: (value: string | null) => (value ? new Date(value).toLocaleString('ru-RU') : '—') },
    { title: 'Состояние', dataIndex: 'is_locked', key: 'is_locked', render: (value: boolean) => <StatusBadge label={value ? 'Заблокирован' : 'Обычное'} tone={value ? 'error' : 'success'} /> },
    {
      title: 'Действия',
      key: 'actions',
      render: (_, item) => (
        <Space>
          <Button icon={<EditOutlined />} onClick={() => openModal(item)} />
          <Popconfirm title={item.is_active ? 'Деактивировать пользователя?' : 'Активировать пользователя?'} onConfirm={() => setUserActive(item.id, !item.is_active).then(load)}>
            <Button icon={<PoweroffOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading && items.length === 0) return <Loader label="Загрузка пользователей" />;
  if (error) return <ErrorState title="Пользователи недоступны" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title="Пользователи" description="Единая модель пользователей для внутренних сотрудников и подрядчиков." actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>Добавить пользователя</Button>} />
      <Section actions={<Space wrap><Input.Search placeholder="Поиск" allowClear onSearch={(search) => setFilters((current) => ({ ...current, search }))} className="sp-search-bar" /><Select allowClear placeholder="Тип" className="cr-filter" onChange={(user_type) => setFilters((current) => ({ ...current, user_type }))} options={[{ value: 'INTERNAL', label: 'INTERNAL' }, { value: 'CONTRACTOR', label: 'CONTRACTOR' }]} /><Select allowClear placeholder="Статус" className="cr-filter" onChange={(is_active) => setFilters((current) => ({ ...current, is_active }))} options={[{ value: true, label: 'Активные' }, { value: false, label: 'Отключенные' }]} /></Space>}>
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} pagination={{ pageSize: 10 }} scroll={{ x: 1300 }} />
      </Section>
      <Modal title={editing ? 'Редактировать пользователя' : 'Новый пользователь'} open={modalOpen} onOk={save} onCancel={() => setModalOpen(false)} confirmLoading={saving} destroyOnHidden width={720}>
        <Form form={form} layout="vertical">
          <div className="admin-form-grid">
            <Form.Item name="username" label="Username" rules={[{ required: true, message: 'Введите username' }]}><Input /></Form.Item>
            <Form.Item name="display_name" label="Имя" rules={[{ required: true, message: 'Введите имя' }]}><Input /></Form.Item>
            <Form.Item name="email" label="Email"><Input /></Form.Item>
            <Form.Item name="user_type" label="Тип" rules={[{ required: true }]}><Select options={[{ value: 'INTERNAL', label: 'INTERNAL' }, { value: 'CONTRACTOR', label: 'CONTRACTOR' }]} /></Form.Item>
            <Form.Item name="auth_source" label="Источник авторизации" rules={[{ required: true }]}><Select options={[{ value: 'LOCAL', label: 'LOCAL' }, { value: 'ADFS', label: 'ADFS' }, { value: 'LDAP', label: 'LDAP' }]} /></Form.Item>
            <Form.Item name="is_active" label="Статус"><Select options={[{ value: true, label: 'Активен' }, { value: false, label: 'Отключен' }]} /></Form.Item>
          </div>
          <Form.Item name="role_ids" label="Роли"><Select mode="multiple" options={roles.map((role) => ({ value: role.id, label: `${role.code} — ${role.name}` }))} /></Form.Item>
          <Form.Item noStyle shouldUpdate={(previous, current) => previous.user_type !== current.user_type}>
            {({ getFieldValue }) => (
              <Form.Item name="contractor_ids" label="Компании" rules={getFieldValue('user_type') === 'CONTRACTOR' ? [{ required: true, message: 'Для подрядчика нужна компания' }] : []}>
                <Select mode="multiple" options={contractors.map((contractor) => ({ value: contractor.id, label: contractor.name }))} />
              </Form.Item>
            )}
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
