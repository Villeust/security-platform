import { EditOutlined, PlusOutlined, StopOutlined } from '@ant-design/icons';
import { Alert, Checkbox, Drawer, Form, Input, Modal, Popconfirm, Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';

import { Button, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import { useAuth } from '../../context/AuthContext';
import { createRole, deactivateRole, getPermissions, getRolePermissions, getRoles, setRolePermissions, updateRole } from './services/adminService';
import type { Permission, Role, Uuid } from './types';

type RoleFormValues = Pick<Role, 'code' | 'name' | 'description'>;

function groupPermissions(permissions: Permission[]) {
  return permissions.reduce<Record<string, Permission[]>>((acc, permission) => {
    acc[permission.resource] = [...(acc[permission.resource] ?? []), permission];
    return acc;
  }, {});
}

export function AdminRolesPage() {
  const [form] = Form.useForm<RoleFormValues>();
  const [items, setItems] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<Uuid[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Role | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const auth = useAuth();

  const load = () => {
    setLoading(true);
    Promise.all([getRoles(), auth.hasPermission('admin.roles.view') ? getPermissions() : Promise.resolve([])])
      .then(([roleData, permissionData]) => {
        setItems(roleData);
        setPermissions(permissionData);
      })
      .catch(() => setError('Не удалось загрузить роли.'))
      .finally(() => setLoading(false));
  };

  const openPermissions = async (role: Role) => {
    setSelectedRole(role);
    try {
      const rolePermissions = await getRolePermissions(role.id);
      setSelectedPermissionIds(rolePermissions.map((permission) => permission.id));
    } catch {
      message.error('Не удалось загрузить права роли');
    }
  };

  const savePermissions = async () => {
    if (!selectedRole) return;
    try {
      await setRolePermissions(selectedRole.id, selectedPermissionIds);
      message.success('Права роли обновлены');
      setSelectedRole(null);
      load();
    } catch {
      message.error('Не удалось сохранить права роли');
    }
  };

  useEffect(load, []);

  const openModal = (item?: Role) => {
    setEditing(item ?? null);
    form.setFieldsValue(item ?? { code: '', name: '', description: '' });
    setModalOpen(true);
  };

  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        await updateRole(editing.id, { name: values.name, description: values.description });
        message.success('Роль обновлена');
      } else {
        await createRole(values);
        message.success('Роль создана');
      }
      setModalOpen(false);
      load();
    } catch {
      message.error('Не удалось сохранить роль');
    } finally {
      setSaving(false);
    }
  };

  const columns: ColumnsType<Role> = [
    { title: 'Code', dataIndex: 'code', key: 'code' },
    { title: 'Название', dataIndex: 'name', key: 'name' },
    { title: 'Описание', dataIndex: 'description', key: 'description', render: (value: string | null) => value ?? '—' },
    { title: 'Пользователи', dataIndex: 'users_count', key: 'users_count' },
    { title: 'Permissions', dataIndex: 'permissions_count', key: 'permissions_count' },
    { title: 'Системная', dataIndex: 'is_system', key: 'is_system', render: (value: boolean) => <StatusBadge label={value ? 'Да' : 'Нет'} tone={value ? 'processing' : 'default'} /> },
    { title: 'Статус', dataIndex: 'is_active', key: 'is_active', render: (value: boolean) => <StatusBadge label={value ? 'Активна' : 'Отключена'} tone={value ? 'success' : 'default'} /> },
    {
      title: 'Действия',
      key: 'actions',
      render: (_, item) => (
        <Space>
          <Button icon={<EditOutlined />} disabled={!auth.hasPermission('admin.roles.manage')} onClick={() => openModal(item)} />
          <Button onClick={() => openPermissions(item)}>Права</Button>
          <Popconfirm title="Деактивировать роль?" disabled={item.is_system} onConfirm={() => deactivateRole(item.id).then(load)}>
            <Button icon={<StopOutlined />} disabled={!auth.hasPermission('admin.roles.manage') || item.is_system || !item.is_active} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading && items.length === 0) return <Loader label="Загрузка ролей" />;
  if (error) return <ErrorState title="Роли недоступны" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title="Роли" description="Базовые роли платформы и пользовательские роли первого этапа." actions={auth.hasPermission('admin.roles.manage') ? <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>Добавить роль</Button> : undefined} />
      <Alert message="Детализированные права будут добавлены на следующем этапе" type="info" showIcon />
      <Section>
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} pagination={{ pageSize: 10 }} />
      </Section>
      <Modal title={editing ? 'Редактировать роль' : 'Новая роль'} open={modalOpen} onOk={save} onCancel={() => setModalOpen(false)} confirmLoading={saving} destroyOnHidden>
        <Form form={form} layout="vertical">
          <Form.Item name="code" label="Code" rules={[{ required: true, message: 'Введите code' }]}><Input disabled={Boolean(editing)} /></Form.Item>
          <Form.Item name="name" label="Название" rules={[{ required: true, message: 'Введите название' }]}><Input /></Form.Item>
          <Form.Item name="description" label="Описание"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
      <Drawer
        title={selectedRole ? `Права роли: ${selectedRole.code}` : 'Права роли'}
        open={Boolean(selectedRole)}
        onClose={() => setSelectedRole(null)}
        width={720}
        extra={auth.hasPermission('admin.roles.manage') ? <Button type="primary" onClick={savePermissions}>Сохранить</Button> : null}
      >
        <Space direction="vertical" className="cr-collaboration-stack">
          {Object.entries(groupPermissions(permissions)).map(([resource, resourcePermissions]) => (
            <div key={resource}>
              <h3>{resource}</h3>
              <Checkbox.Group
                className="admin-permission-group"
                value={selectedPermissionIds}
                disabled={!auth.hasPermission('admin.roles.manage')}
                options={resourcePermissions.map((permission) => ({ value: permission.id, label: `${permission.code} — ${permission.name}` }))}
                onChange={(values) => setSelectedPermissionIds(values.map(String))}
              />
            </div>
          ))}
          {selectedRole?.is_system ? <Alert message="Системные роли можно просматривать. Для PLATFORM_ADMIN нельзя снять критические системные permissions." type="warning" showIcon /> : null}
        </Space>
      </Drawer>
    </div>
  );
}
