import { EyeOutlined, FileAddOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { Segmented, Space, Typography, message } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, ErrorState, Loader } from '../../components/design-system';
import { AssignmentStatusBadge, ContractorEmptyState, DataTable, PortalPage, SectionCard } from './components';
import { formatDate } from './constants';
import { getContractorRequests, getContractorTasks, updateContractorAssignmentStatus } from './services';
import type { ContractorTask } from './types';

const tabs = [
  { key: 'ASSIGNED', label: 'Ожидают' },
  { key: 'ACCEPTED', label: 'Приняты' },
  { key: 'IN_PROGRESS', label: 'В работе' },
  { key: 'RESULT_REQUIRED', label: 'Требуют результата' },
  { key: 'OVERDUE', label: 'Просрочены' },
  { key: 'COMPLETED', label: 'Завершены' },
];

export function ContractorTasksPage() {
  const [items, setItems] = useState<ContractorTask[]>([]);
  const [requestNumbers, setRequestNumbers] = useState<Map<string, string>>(new Map());
  const [tab, setTab] = useState('ASSIGNED');
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setFailed(false);
    Promise.all([getContractorTasks(), getContractorRequests()])
      .then(([taskData, requestData]) => {
        setItems(taskData);
        setRequestNumbers(new Map(requestData.flatMap((request) => request.assignments.map((assignment) => [assignment.id, request.request_number ?? request.id]))));
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const filtered = useMemo(() => {
    if (tab === 'RESULT_REQUIRED') return items.filter((item) => item.status === 'IN_PROGRESS');
    if (tab === 'OVERDUE') return items.filter((item) => item.status !== 'COMPLETED' && item.status !== 'CANCELLED');
    return items.filter((item) => item.status === tab);
  }, [items, tab]);

  const counts = useMemo(() => new Map(tabs.map((item) => [item.key, item.key === 'RESULT_REQUIRED' ? items.filter((task) => task.status === 'IN_PROGRESS').length : item.key === 'OVERDUE' ? items.filter((task) => task.status !== 'COMPLETED' && task.status !== 'CANCELLED').length : items.filter((task) => task.status === item.key).length])), [items]);

  const updateStatus = async (task: ContractorTask, status: string) => {
    await updateContractorAssignmentStatus(task.id, status);
    message.success('Статус задачи обновлён');
    load();
  };

  return (
    <PortalPage title="Задачи" description="Рабочий экран выполнения назначений">
      <SectionCard>
        <Segmented className="contractor-segmented" value={tab} onChange={(value) => setTab(String(value))} options={tabs.map((item) => ({ value: item.key, label: `${item.label} (${counts.get(item.key) ?? 0})` }))} />
      </SectionCard>

      {failed ? <ErrorState title="Не удалось загрузить задачи" description="Повторите попытку позже." /> : null}
      {loading ? <Loader label="Загрузка задач" /> : (
        <SectionCard className="contractor-table-card" title="Задачи" description={`Категория: ${tabs.find((item) => item.key === tab)?.label}`}>
          {filtered.length ? (
            <DataTable
              rowKey="id"
              dataSource={filtered}
              pagination={{ pageSize: 10, size: 'small' }}
              columns={[
                { title: 'Номер заявки', render: (_, task) => requestNumbers.get(task.id) ?? 'Без номера' },
                { title: 'Направление', dataIndex: 'work_type_id', render: () => 'Направление работ' },
                { title: 'Объект', render: () => 'Объект заявки' },
                { title: 'Статус', dataIndex: 'status', render: (status) => <AssignmentStatusBadge status={status} /> },
                { title: 'Срок', dataIndex: 'completed_at', render: (value, task) => formatDate(value ?? task.updated_at) },
                { title: 'Назначено', dataIndex: 'assigned_at', render: (value) => formatDate(value, true) },
                { title: 'Результат', render: (_, task) => task.status === 'COMPLETED' ? <Typography.Text type="success">Загружен</Typography.Text> : 'Требуется' },
                {
                  title: 'Действие',
                  render: (_, task) => (
                    <Space wrap>
                      {task.status === 'ASSIGNED' ? <Button onClick={() => void updateStatus(task, 'ACCEPTED')}>Принять</Button> : null}
                      {task.status === 'ACCEPTED' ? <Button icon={<PlayCircleOutlined />} onClick={() => void updateStatus(task, 'IN_PROGRESS')}>Начать</Button> : null}
                      {task.status === 'IN_PROGRESS' ? <Button icon={<FileAddOutlined />}>Результат</Button> : null}
                      {task.status === 'IN_PROGRESS' ? <Button type="primary" onClick={() => void updateStatus(task, 'COMPLETED')}>Завершить</Button> : null}
                      <Button icon={<EyeOutlined />} onClick={() => navigate('/contractor/requests')}>Заявка</Button>
                    </Space>
                  ),
                },
              ]}
            />
          ) : (
            <ContractorEmptyState title="Нет задач" description={`В категории «${tabs.find((item) => item.key === tab)?.label}» сейчас нет задач.`} actionLabel="Обновить" onAction={load} />
          )}
        </SectionCard>
      )}
    </PortalPage>
  );
}
