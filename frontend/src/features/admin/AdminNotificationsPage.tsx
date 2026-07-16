import { CheckCircleOutlined, EyeOutlined } from '@ant-design/icons';
import { Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';

import { Button, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import { getNotifications, markNotificationRead, resolveNotification } from './services/adminService';
import type { AdminNotification } from './types';

export function AdminNotificationsPage() {
  const [items, setItems] = useState<AdminNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    getNotifications()
      .then(setItems)
      .catch(() => setError('Не удалось загрузить административные уведомления.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const columns: ColumnsType<AdminNotification> = [
    { title: 'Дата', dataIndex: 'created_at', key: 'created_at', render: (value: string) => new Date(value).toLocaleString('ru-RU') },
    { title: 'Тип', dataIndex: 'type', key: 'type' },
    { title: 'Важность', dataIndex: 'severity', key: 'severity', render: (value: string) => <StatusBadge label={value} tone={value === 'HIGH' || value === 'CRITICAL' ? 'error' : value === 'WARNING' ? 'warning' : 'processing'} /> },
    { title: 'Заголовок', dataIndex: 'title', key: 'title' },
    { title: 'Сообщение', dataIndex: 'message', key: 'message' },
    { title: 'Статус', key: 'status', render: (_, item) => <Space><StatusBadge label={item.is_read ? 'Прочитано' : 'Новое'} tone={item.is_read ? 'default' : 'processing'} /><StatusBadge label={item.is_resolved ? 'Решено' : 'Открыто'} tone={item.is_resolved ? 'success' : 'warning'} /></Space> },
    {
      title: 'Действия',
      key: 'actions',
      render: (_, item) => (
        <Space>
          <Button icon={<EyeOutlined />} disabled={item.is_read} onClick={() => markNotificationRead(item.id).then(() => { message.success('Отмечено как прочитанное'); load(); })} />
          <Button icon={<CheckCircleOutlined />} disabled={item.is_resolved} onClick={() => resolveNotification(item.id).then(() => { message.success('Уведомление закрыто'); load(); })} />
        </Space>
      ),
    },
  ];

  if (loading && items.length === 0) return <Loader label="Загрузка уведомлений" />;
  if (error) return <ErrorState title="Уведомления недоступны" description={error} />;

  return (
    <div className="sp-page">
      <PageHeader title="Административные уведомления" description="События безопасности учётных записей, паролей и подключений." />
      <Section>
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} pagination={{ pageSize: 10 }} scroll={{ x: 1200 }} />
      </Section>
    </div>
  );
}
