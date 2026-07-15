import { EditOutlined, PlusOutlined, PoweroffOutlined } from '@ant-design/icons';
import { Form, Input, Modal, Popconfirm, Select, Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';

import { Button, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import { createContractor, getContractors, setContractorActive, updateContractor } from './services/adminService';
import type { AdminContractor } from './types';

type ContractorFormValues = Pick<AdminContractor, 'name' | 'code' | 'email' | 'phone' | 'is_active'>;

export function AdminContractorsPage() {
  const [form] = Form.useForm<ContractorFormValues>();
  const [items, setItems] = useState<AdminContractor[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [isActive, setIsActive] = useState<boolean | undefined>();
  const [editing, setEditing] = useState<AdminContractor | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const load = () => {
    setLoading(true);
    getContractors({ search: search || undefined, is_active: isActive })
      .then(setItems)
      .catch(() => setError('Не удалось загрузить компании.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [search, isActive]);

  const openModal = (item?: AdminContractor) => {
    setEditing(item ?? null);
    form.setFieldsValue(item ?? { is_active: true });
    setModalOpen(true);
  };

  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        await updateContractor(editing.id, values);
        message.success('Компания обновлена');
      } else {
        await createContractor(values);
        message.success('Компания создана');
      }
      setModalOpen(false);
      load();
    } catch {
      message.error('Не удалось сохранить компанию');
    } finally {
      setSaving(false);
    }
  };

  const columns: ColumnsType<AdminContractor> = [
    { title: 'Название', dataIndex: 'name', key: 'name' },
    { title: 'Код', dataIndex: 'code', key: 'code' },
    { title: 'Email', dataIndex: 'email', key: 'email', render: (value: string | null) => value ?? '—' },
    { title: 'Телефон', dataIndex: 'phone', key: 'phone', render: (value: string | null) => value ?? '—' },
    { title: 'Пользователи', dataIndex: 'users_count', key: 'users_count' },
    { title: 'Зоны', dataIndex: 'responsibilities_count', key: 'responsibilities_count' },
    { title: 'Статус', dataIndex: 'is_active', key: 'is_active', render: (value: boolean) => <StatusBadge label={value ? 'Активна' : 'Отключена'} tone={value ? 'success' : 'default'} /> },
    { title: 'Создана', dataIndex: 'created_at', key: 'created_at', render: (value: string) => new Date(value).toLocaleString('ru-RU') },
    {
      title: 'Действия',
      key: 'actions',
      render: (_, item) => (
        <Space>
          <Button icon={<EditOutlined />} onClick={() => openModal(item)} />
          <Popconfirm title={item.is_active ? 'Деактивировать компанию?' : 'Активировать компанию?'} onConfirm={() => setContractorActive(item.id, !item.is_active).then(load)}>
            <Button icon={<PoweroffOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading && items.length === 0) return <Loader label="Загрузка компаний" />;
  if (error) return <ErrorState title="Компании недоступны" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title="Компании" description="Управление подрядными организациями Security Platform." actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>Добавить компанию</Button>} />
      <Section actions={<Space wrap><Input.Search placeholder="Поиск" allowClear onSearch={setSearch} className="sp-search-bar" /><Select allowClear placeholder="Статус" className="cr-filter" onChange={setIsActive} options={[{ value: true, label: 'Активные' }, { value: false, label: 'Отключенные' }]} /></Space>}>
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} pagination={{ pageSize: 10 }} />
      </Section>
      <Modal title={editing ? 'Редактировать компанию' : 'Новая компания'} open={modalOpen} onOk={save} onCancel={() => setModalOpen(false)} confirmLoading={saving} destroyOnHidden>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Название" rules={[{ required: true, message: 'Введите название' }]}><Input /></Form.Item>
          <Form.Item name="code" label="Код" rules={[{ required: true, message: 'Введите код' }]}><Input /></Form.Item>
          <Form.Item name="email" label="Email"><Input /></Form.Item>
          <Form.Item name="phone" label="Телефон"><Input /></Form.Item>
          <Form.Item name="is_active" label="Статус" initialValue={true}><Select options={[{ value: true, label: 'Активна' }, { value: false, label: 'Отключена' }]} /></Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
