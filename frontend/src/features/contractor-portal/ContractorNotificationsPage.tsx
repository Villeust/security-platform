import { BellOutlined, CheckOutlined } from '@ant-design/icons';
import { Card, List, Segmented, Select, Space, Typography } from 'antd';
import { useEffect, useMemo, useState } from 'react';

import { Button, ErrorState, Loader, StatusBadge } from '../../components/design-system';
import { ContractorEmptyState, PortalPage } from './components';
import { formatDate } from './constants';
import { getContractorNotifications } from './services';
import type { ContractorNotification } from './types';

export function ContractorNotificationsPage() {
  const [items, setItems] = useState<ContractorNotification[]>([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = () => {
    setLoading(true);
    setFailed(false);
    getContractorNotifications().then(setItems).catch(() => setFailed(true)).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const filtered = useMemo(() => items.filter(() => filter === 'all' || filter === 'unread' || filter === 'high'), [items, filter]);

  return (
    <PortalPage title="Уведомления" description="События и напоминания по заявкам вашей компании">
      <Card className="contractor-card">
        <Space wrap>
          <Segmented value={filter} onChange={(value) => setFilter(String(value))} options={[{ value: 'all', label: 'Все' }, { value: 'unread', label: 'Непрочитанные' }, { value: 'high', label: 'Высокий приоритет' }]} />
          <Select className="contractor-filter" allowClear placeholder="Тип уведомления" options={[]} />
          <Button icon={<CheckOutlined />}>Отметить все как прочитанные</Button>
        </Space>
      </Card>

      {failed ? <ErrorState title="Не удалось загрузить уведомления" description="Повторите попытку позже." /> : null}
      {loading ? <Loader label="Загрузка уведомлений" /> : (
        <Card className="contractor-card">
          {filtered.length ? (
            <List
              dataSource={filtered}
              renderItem={(item) => (
                <List.Item className="contractor-notification">
                  <List.Item.Meta
                    avatar={<span className="contractor-empty-icon"><BellOutlined /></span>}
                    title={<Space><Typography.Text strong>{item.title}</Typography.Text><StatusBadge label="Информация" tone="processing" /></Space>}
                    description={<Space direction="vertical"><span>{item.message}</span><Typography.Text type="secondary">{formatDate(item.created_at, true)}</Typography.Text></Space>}
                  />
                  <Button>Открыть заявку</Button>
                </List.Item>
              )}
            />
          ) : (
            <ContractorEmptyState title="Новых уведомлений нет" description="Важные события и напоминания появятся здесь." />
          )}
        </Card>
      )}
    </PortalPage>
  );
}
