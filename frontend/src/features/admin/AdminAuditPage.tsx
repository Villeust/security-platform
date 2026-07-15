import { EyeOutlined } from '@ant-design/icons';
import { Drawer, Input, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';

import { Button, ErrorState, Loader, PageHeader, Section, Table } from '../../components/design-system';
import { getAudit } from './services/adminService';
import type { AuditLog } from './types';

export function AdminAuditPage() {
  const [items, setItems] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string | undefined>>({});
  const [selected, setSelected] = useState<AuditLog | null>(null);

  const load = () => {
    setLoading(true);
    getAudit(filters)
      .then(setItems)
      .catch(() => setError('Не удалось загрузить журнал действий.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [filters]);

  const columns: ColumnsType<AuditLog> = [
    { title: 'Дата', dataIndex: 'created_at', key: 'created_at', render: (value: string) => new Date(value).toLocaleString('ru-RU') },
    { title: 'Actor', dataIndex: 'actor_type', key: 'actor_type' },
    { title: 'Действие', dataIndex: 'action', key: 'action' },
    { title: 'Сущность', dataIndex: 'entity_type', key: 'entity_type' },
    { title: 'Entity ID', dataIndex: 'entity_id', key: 'entity_id', render: (value: string | null) => value ?? '—' },
    {
      title: 'Изменения',
      key: 'changes',
      render: (_, item) => (item.old_data || item.new_data ? 'Есть данные изменений' : '—'),
    },
    { title: 'Просмотр', key: 'actions', render: (_, item) => <Button icon={<EyeOutlined />} onClick={() => setSelected(item)} /> },
  ];

  if (loading && items.length === 0) return <Loader label="Загрузка аудита" />;
  if (error) return <ErrorState title="Журнал недоступен" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title="Журнал действий" description="Административные изменения и транзакционные события справочников." />
      <Section actions={<Space wrap><Input.Search placeholder="Действие" allowClear onSearch={(action) => setFilters((current) => ({ ...current, action }))} className="sp-search-bar" /><Input.Search placeholder="Сущность" allowClear onSearch={(entity_type) => setFilters((current) => ({ ...current, entity_type }))} className="sp-search-bar" /></Space>}>
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} pagination={{ pageSize: 10 }} />
      </Section>
      <Drawer title="Детали события" open={Boolean(selected)} onClose={() => setSelected(null)} width={640}>
        <h3>Old data</h3>
        <pre className="admin-json">{JSON.stringify(selected?.old_data ?? null, null, 2)}</pre>
        <h3>New data</h3>
        <pre className="admin-json">{JSON.stringify(selected?.new_data ?? null, null, 2)}</pre>
      </Drawer>
    </div>
  );
}
