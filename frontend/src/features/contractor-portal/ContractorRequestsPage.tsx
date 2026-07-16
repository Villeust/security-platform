import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { Checkbox, Input, Select, Space, Typography } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useMemo, useState } from 'react';

import { Button, ErrorState, Loader } from '../../components/design-system';
import type { ContractorRequest, RequestStatus } from '../contractor-requests/types/api';
import { AssignmentStatusBadge, ContractorEmptyState, DataTable, FilterBar, PortalPage, PriorityBadge, RequestStatusBadge, SectionCard } from './components';
import { assignmentStatusLabel, formatDate, isOverdue, requestStatusLabel } from './constants';
import { getContractorMe, getContractorRequests } from './services';
import type { ContractorMe } from './types';

export function ContractorRequestsPage() {
  const [items, setItems] = useState<ContractorRequest[]>([]);
  const [profile, setProfile] = useState<ContractorMe | null>(null);
  const [status, setStatus] = useState<string | undefined>();
  const [assignmentStatus, setAssignmentStatus] = useState<string | undefined>();
  const [search, setSearch] = useState<string | undefined>();
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    setFailed(false);
    Promise.all([getContractorRequests({ status, assignment_status: assignmentStatus, search }), getContractorMe()])
      .then(([requestData, profileData]) => {
        setItems(requestData);
        setProfile(profileData);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, [status, assignmentStatus, search]);

  const visibleItems = useMemo(() => overdueOnly ? items.filter((item) => isOverdue(item.desired_completion_date) && item.status !== 'COMPLETED' && item.status !== 'CLOSED') : items, [items, overdueOnly]);

  const reset = () => {
    setStatus(undefined);
    setAssignmentStatus(undefined);
    setSearch(undefined);
    setOverdueOnly(false);
  };

  return (
    <PortalPage title="Заявки" description="Заявки, назначенные вашей компании">
      <FilterBar>
        <Input.Search className="contractor-search" allowClear placeholder="Поиск по номеру или названию" value={search} onChange={(event) => setSearch(event.target.value || undefined)} onSearch={(value) => setSearch(value || undefined)} />
        {profile && profile.contractors.length > 1 ? <Select className="contractor-filter" placeholder="Компания" options={profile.contractors.map((item) => ({ value: item.id, label: item.name }))} disabled /> : null}
        <Select className="contractor-filter" allowClear placeholder="Статус заявки" value={status} onChange={setStatus} options={Object.entries(requestStatusLabel).map(([value, label]) => ({ value, label }))} />
        <Select className="contractor-filter" allowClear placeholder="Статус назначения" value={assignmentStatus} onChange={setAssignmentStatus} options={Object.entries(assignmentStatusLabel).map(([value, label]) => ({ value, label }))} />
        <Checkbox checked={overdueOnly} onChange={(event) => setOverdueOnly(event.target.checked)}>Просрочено</Checkbox>
        <Button icon={<ReloadOutlined />} onClick={reset}>Сбросить</Button>
      </FilterBar>

      {failed ? <ErrorState title="Не удалось загрузить заявки" description="Повторите попытку позже." /> : null}
      {loading ? <Loader label="Загрузка заявок" /> : (
        <SectionCard className="contractor-table-card" title="Рабочий список" description={`Показано: ${visibleItems.length}`}>
          {visibleItems.length ? (
            <DataTable
              rowKey="id"
              dataSource={visibleItems}
              pagination={{ pageSize: 10, showSizeChanger: true, size: 'small' }}
              onRow={(record) => ({ onDoubleClick: () => navigate(`/contractor/requests/${record.id}`) })}
              columns={[
                { title: 'Номер', dataIndex: 'request_number', sorter: (a, b) => (a.request_number ?? '').localeCompare(b.request_number ?? ''), render: (value, record) => <Link to={`/contractor/requests/${record.id}`}>{value ?? 'Без номера'}</Link> },
                { title: 'Название', dataIndex: 'title', sorter: (a, b) => a.title.localeCompare(b.title) },
                { title: 'Объект', dataIndex: 'facility_id', render: () => 'Объект заявки' },
                { title: 'Направление', render: (_, record) => record.work_type_ids.length ? `${record.work_type_ids.length} направл.` : '—' },
                { title: 'Назначение', render: (_, record) => record.assignments[0] ? <AssignmentStatusBadge status={record.assignments[0].status} /> : '—' },
                { title: 'Заявка', dataIndex: 'status', render: (value: RequestStatus) => <RequestStatusBadge status={value} /> },
                { title: 'Приоритет', dataIndex: 'priority', render: (value) => <PriorityBadge value={value} /> },
                { title: 'Срок', dataIndex: 'desired_completion_date', sorter: (a, b) => (a.desired_completion_date ?? '').localeCompare(b.desired_completion_date ?? ''), render: (value) => isOverdue(value) ? <Typography.Text type="danger">{formatDate(value)}</Typography.Text> : formatDate(value) },
                { title: 'Назначено', render: (_, record) => formatDate(record.assignments[0]?.assigned_at) },
                { title: 'Действия', render: (_, record) => <Button icon={<EyeOutlined />} onClick={() => navigate(`/contractor/requests/${record.id}`)}>Открыть</Button> },
              ]}
            />
          ) : (
            <ContractorEmptyState title="Нет заявок" description="Для вашей компании пока нет назначенных заявок." actionLabel="Обновить" onAction={load} />
          )}
        </SectionCard>
      )}
    </PortalPage>
  );
}
