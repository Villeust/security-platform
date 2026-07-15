import { EditOutlined, PlusOutlined } from '@ant-design/icons';
import { Form, Input, InputNumber, Modal, Select, Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';

import { Button, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import { createAdminReference, getAdminReference, updateAdminReference } from './services/adminService';
import type { AdminContractor, AdminReferenceRecord, Uuid } from './types';

type ReferenceResource = 'cities' | 'facilities' | 'premises' | 'responsibilities' | 'work-types';

type Props = {
  resource: ReferenceResource;
  title: string;
  description: string;
};

type FormField = {
  name: keyof AdminReferenceRecord;
  label: string;
  type?: 'text' | 'number' | 'boolean' | 'select';
  required?: boolean;
  options?: { value: string | number | boolean; label: string }[];
};

const resourceFields: Record<ReferenceResource, (refs: ReferenceMaps) => FormField[]> = {
  cities: () => [
    { name: 'name', label: 'Название', required: true },
    { name: 'code', label: 'Код', required: true },
    { name: 'is_active', label: 'Статус', type: 'boolean' },
  ],
  facilities: (refs) => [
    { name: 'city_id', label: 'Город', type: 'select', required: true, options: refs.cities },
    { name: 'name', label: 'Название', required: true },
    { name: 'address', label: 'Адрес', required: true },
    { name: 'code', label: 'Код', required: true },
    { name: 'is_active', label: 'Статус', type: 'boolean' },
  ],
  premises: (refs) => [
    { name: 'facility_id', label: 'Объект', type: 'select', required: true, options: refs.facilities },
    { name: 'name', label: 'Название', required: true },
    { name: 'number', label: 'Номер' },
    { name: 'category', label: 'Категория' },
    { name: 'owner_name', label: 'Контакт' },
    { name: 'owner_email', label: 'Email' },
    { name: 'owner_phone', label: 'Телефон' },
    { name: 'has_access_control', label: 'СКУД', type: 'boolean' },
    { name: 'is_active', label: 'Статус', type: 'boolean' },
  ],
  responsibilities: (refs) => [
    { name: 'contractor_id', label: 'Компания', type: 'select', required: true, options: refs.contractors },
    { name: 'city_id', label: 'Город', type: 'select', options: refs.cities },
    { name: 'facility_id', label: 'Объект', type: 'select', options: refs.facilities },
    { name: 'work_type_id', label: 'Направление работ', type: 'select', required: true, options: refs.workTypes },
    { name: 'priority', label: 'Приоритет', type: 'number' },
    { name: 'is_active', label: 'Статус', type: 'boolean' },
  ],
  'work-types': () => [
    { name: 'name', label: 'Название', required: true },
    { name: 'code', label: 'Код', required: true },
    { name: 'requires_premise', label: 'Требует помещение', type: 'boolean' },
    { name: 'is_active', label: 'Статус', type: 'boolean' },
  ],
};

type ReferenceMaps = {
  cities: { value: Uuid; label: string }[];
  facilities: { value: Uuid; label: string }[];
  contractors: { value: Uuid; label: string }[];
  workTypes: { value: Uuid; label: string }[];
};

function cleanPayload(values: AdminReferenceRecord) {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, value === '' ? null : value]).filter(([, value]) => value !== undefined),
  );
}

export function AdminReferencePage({ resource, title, description }: Props) {
  const [form] = Form.useForm<AdminReferenceRecord>();
  const [items, setItems] = useState<AdminReferenceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [isActive, setIsActive] = useState<boolean | undefined>();
  const [editing, setEditing] = useState<AdminReferenceRecord | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [cities, setCities] = useState<AdminReferenceRecord[]>([]);
  const [facilities, setFacilities] = useState<AdminReferenceRecord[]>([]);
  const [contractors, setContractors] = useState<AdminContractor[]>([]);
  const [workTypes, setWorkTypes] = useState<AdminReferenceRecord[]>([]);

  const refs = useMemo<ReferenceMaps>(
    () => ({
      cities: cities.map((item) => ({ value: item.id, label: item.name ?? item.code ?? item.id })),
      facilities: facilities.map((item) => ({ value: item.id, label: item.name ?? item.code ?? item.id })),
      contractors: contractors.map((item) => ({ value: item.id, label: item.name })),
      workTypes: workTypes.map((item) => ({ value: item.id, label: item.name ?? item.code ?? item.id })),
    }),
    [cities, facilities, contractors, workTypes],
  );

  const fields = resourceFields[resource](refs);

  const load = () => {
    setLoading(true);
    Promise.all([
      getAdminReference<AdminReferenceRecord>(resource, { search: search || undefined, is_active: isActive }),
      getAdminReference<AdminReferenceRecord>('cities'),
      getAdminReference<AdminReferenceRecord>('facilities'),
      getAdminReference<AdminContractor>('contractors'),
      getAdminReference<AdminReferenceRecord>('work-types'),
    ])
      .then(([data, cityData, facilityData, contractorData, workTypeData]) => {
        setItems(data);
        setCities(cityData);
        setFacilities(facilityData);
        setContractors(contractorData);
        setWorkTypes(workTypeData);
      })
      .catch(() => setError('Не удалось загрузить справочник.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [resource, search, isActive]);

  const openModal = (item?: AdminReferenceRecord) => {
    setEditing(item ?? null);
    form.setFieldsValue(item ?? { is_active: true, has_access_control: false, requires_premise: false, priority: 100 });
    setModalOpen(true);
  };

  const save = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        await updateAdminReference<AdminReferenceRecord>(resource, editing.id, cleanPayload(values));
        message.success('Запись обновлена');
      } else {
        await createAdminReference<AdminReferenceRecord>(resource, cleanPayload(values));
        message.success('Запись создана');
      }
      setModalOpen(false);
      load();
    } catch {
      message.error('Не удалось сохранить запись');
    } finally {
      setSaving(false);
    }
  };

  const labelOf = (options: { value: Uuid; label: string }[], value?: Uuid | null) => options.find((option) => option.value === value)?.label ?? value ?? '—';

  const columns: ColumnsType<AdminReferenceRecord> = [
    { title: 'Название', dataIndex: 'name', key: 'name', render: (value: string | undefined, item: AdminReferenceRecord) => value ?? item.code ?? item.id },
    { title: 'Код', dataIndex: 'code', key: 'code', render: (value: string | undefined) => value ?? '—' },
    { title: 'Город', dataIndex: 'city_id', key: 'city_id', render: (value: Uuid | null | undefined) => labelOf(refs.cities, value) },
    { title: 'Объект', dataIndex: 'facility_id', key: 'facility_id', render: (value: Uuid | null | undefined) => labelOf(refs.facilities, value) },
    { title: 'Компания', dataIndex: 'contractor_id', key: 'contractor_id', render: (value: Uuid | null | undefined) => labelOf(refs.contractors, value) },
    { title: 'Направление', dataIndex: 'work_type_id', key: 'work_type_id', render: (value: Uuid | null | undefined) => labelOf(refs.workTypes, value) },
    { title: 'Приоритет', dataIndex: 'priority', key: 'priority', render: (value: number | undefined) => value ?? '—' },
    { title: 'Статус', dataIndex: 'is_active', key: 'is_active', render: (value: boolean | undefined) => <StatusBadge label={value === false ? 'Отключена' : 'Активна'} tone={value === false ? 'default' : 'success'} /> },
    { title: 'Действия', key: 'actions', render: (_: unknown, item: AdminReferenceRecord) => <Button icon={<EditOutlined />} onClick={() => openModal(item)} /> },
  ].filter((column) => {
    if (resource === 'cities' || resource === 'work-types') return !['city_id', 'facility_id', 'contractor_id', 'work_type_id', 'priority'].includes(String(column.key));
    if (resource === 'facilities') return !['facility_id', 'contractor_id', 'work_type_id', 'priority'].includes(String(column.key));
    if (resource === 'premises') return !['contractor_id', 'work_type_id', 'priority', 'code'].includes(String(column.key));
    return true;
  });

  if (loading && items.length === 0) return <Loader label={`Загрузка: ${title}`} />;
  if (error) return <ErrorState title="Справочник недоступен" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title={title} description={description} actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>Добавить</Button>} />
      <Section actions={<Space wrap><Input.Search placeholder="Поиск" allowClear onSearch={setSearch} className="sp-search-bar" /><Select allowClear placeholder="Статус" className="cr-filter" onChange={setIsActive} options={[{ value: true, label: 'Активные' }, { value: false, label: 'Отключенные' }]} /></Space>}>
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} pagination={{ pageSize: 10 }} scroll={{ x: 1100 }} />
      </Section>
      <Modal title={editing ? 'Редактировать запись' : 'Новая запись'} open={modalOpen} onOk={save} onCancel={() => setModalOpen(false)} confirmLoading={saving} destroyOnHidden width={720}>
        <Form form={form} layout="vertical">
          <div className="admin-form-grid">
            {fields.map((field) => (
              <Form.Item key={String(field.name)} name={field.name} label={field.label} rules={field.required ? [{ required: true, message: 'Заполните поле' }] : []}>
                {field.type === 'select' ? <Select allowClear options={field.options} /> : null}
                {field.type === 'number' ? <InputNumber min={0} className="admin-full-width" /> : null}
                {field.type === 'boolean' ? <Select options={[{ value: true, label: 'Да' }, { value: false, label: 'Нет' }]} /> : null}
                {!field.type || field.type === 'text' ? <Input /> : null}
              </Form.Item>
            ))}
          </div>
        </Form>
      </Modal>
    </div>
  );
}
