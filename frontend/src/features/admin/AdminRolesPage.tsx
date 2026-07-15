import { EditOutlined, PlusOutlined, StopOutlined } from '@ant-design/icons';
import { Alert, Form, Input, Modal, Popconfirm, Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';

import { Button, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import { createRole, deactivateRole, getRoles, updateRole } from './services/adminService';
import type { Role } from './types';

type RoleFormValues = Pick<Role, 'code' | 'name' | 'description'>;

export function AdminRolesPage() {
  const [form] = Form.useForm<RoleFormValues>();
  const [items, setItems] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Role | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const load = () => {
    setLoading(true);
    getRoles()
      .then(setItems)
      .catch(() => setError('Не удалось загрузить роли.'))
      .finally(() => setLoading(false));
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
    { title: 'Системная', dataIndex: 'is_system', key: 'is_system', render: (value: boolean) => <StatusBadge label={value ? 'Да' : 'Нет'} tone={value ? 'processing' : 'default'} /> },
    { title: 'Статус', dataIndex: 'is_active', key: 'is_active', render: (value: boolean) => <StatusBadge label={value ? 'Активна' : 'Отключена'} tone={value ? 'success' : 'default'} /> },
    {
      title: 'Действия',
      key: 'actions',
      render: (_, item) => (
        <Space>
          <Button icon={<EditOutlined />} onClick={() => openModal(item)} />
          <Popconfirm title="Деактивировать роль?" disabled={item.is_system} onConfirm={() => deactivateRole(item.id).then(load)}>
            <Button icon={<StopOutlined />} disabled={item.is_system || !item.is_active} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading && items.length === 0) return <Loader label="Загрузка ролей" />;
  if (error) return <ErrorState title="Роли недоступны" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title="Роли" description="Базовые роли платформы и пользовательские роли первого этапа." actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>Добавить роль</Button>} />
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
    </div>
  );
}
