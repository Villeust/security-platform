import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { Select, Space, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Button, Card, EmptyState, ErrorState, Loader, PageHeader, SearchBar, Section, Table } from '../../components/design-system';
import { useAuth } from '../../context/AuthContext';
import { RequestStatusBadge } from './components/RequestStatusBadge';
import { useReferenceData } from './hooks/useReferenceData';
import { useRequests } from './hooks/useRequests';
import type { ContractorRequest, RequestListParams, RequestStatus, Uuid } from './types/api';
import { contractorName, facilityName, formatDate, getWorkTypeLabel, labelsByIds } from './utils';

type Filters = {
  search?: string;
  status?: RequestStatus;
  priority?: string;
  city_id?: Uuid;
  facility_id?: Uuid;
  work_type_id?: Uuid;
};

const requestStatuses: RequestStatus[] = ['DRAFT', 'NEW', 'PARTIALLY_ASSIGNED', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CLOSED', 'CANCELLED'];

export function ContractorRequestsListPage() {
  const navigate = useNavigate();
  const auth = useAuth();
  const referenceData = useReferenceData();
  const [filters, setFilters] = useState<Filters>({});
  const requestParams: RequestListParams = useMemo(
    () => ({
      ...filters,
      limit: 100,
      sort_by: 'created_at',
      sort_order: 'desc',
    }),
    [filters],
  );
  const { requests, isLoading, error, reload } = useRequests(requestParams);

  const columns: ColumnsType<ContractorRequest> = [
    {
      title: 'Номер',
      dataIndex: 'request_number',
      key: 'request_number',
      render: (_value, record) => <Link to={`/applications/contractor-requests/${record.id}`}>{record.request_number ?? record.id}</Link>,
    },
    { title: 'Заголовок', dataIndex: 'title', key: 'title' },
    {
      title: 'Объект',
      key: 'facility',
      render: (_value, record) => (record.facility_id ? facilityName(record.facility_id, referenceData.facilities) : '—'),
    },
    {
      title: 'Направления',
      key: 'work_types',
      render: (_value, record) => (
        <Space wrap>
          {labelsByIds(record.work_type_ids, referenceData.workTypes, getWorkTypeLabel).map((label) => (
            <Tag key={label}>{label}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: 'Подрядчики',
      key: 'contractors',
      render: (_value, record) => (
        <Space direction="vertical" size={2}>
          {record.assignments.map((assignment) => (
            <span key={assignment.id}>{contractorName(assignment.contractor_id, referenceData.contractors)}</span>
          ))}
        </Space>
      ),
    },
    { title: 'Приоритет', dataIndex: 'priority', key: 'priority', render: (value: string | null) => value ?? '—' },
    { title: 'Статус', dataIndex: 'status', key: 'status', render: (status: RequestStatus) => <RequestStatusBadge status={status} /> },
    { title: 'Желаемый срок', dataIndex: 'desired_completion_date', key: 'desired_completion_date', render: (value: string | null) => formatDate(value) },
    { title: 'Создано', dataIndex: 'created_at', key: 'created_at', render: (value: string) => formatDate(value) },
  ];

  if (isLoading || referenceData.isLoading) {
    return <Loader label="Загрузка заявок" />;
  }

  if (error || referenceData.error) {
    return <ErrorState title="Не удалось загрузить модуль" description={error ?? referenceData.error ?? undefined} />;
  }

  return (
    <div className="sp-page">
      <PageHeader
        title="Заявки подрядчикам"
        description="Рабочий список заявок Contractor Requests с серверными фильтрами."
        actions={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => reload()}>
              Обновить
            </Button>
            {auth.hasPermission('requests.create') ? (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/applications/contractor-requests/new')}>
                Создать заявку
              </Button>
            ) : null}
          </Space>
        }
      />
      <Card>
        <div className="cr-toolbar">
          <SearchBar placeholder="Поиск по номеру, заголовку или описанию" onSearch={(search) => setFilters((current) => ({ ...current, search: search || undefined }))} />
          <Select
            allowClear
            placeholder="Статус"
            className="cr-filter"
            options={requestStatuses.map((status) => ({ label: status, value: status }))}
            onChange={(status?: RequestStatus) => setFilters((current) => ({ ...current, status }))}
          />
          <Select
            allowClear
            placeholder="Приоритет"
            className="cr-filter"
            options={[
              { label: 'Низкий', value: 'low' },
              { label: 'Обычный', value: 'normal' },
              { label: 'Высокий', value: 'high' },
            ]}
            onChange={(priority?: string) => setFilters((current) => ({ ...current, priority }))}
          />
          <Select
            allowClear
            placeholder="Город"
            className="cr-filter"
            options={referenceData.cities.map((city) => ({ label: city.name, value: city.id }))}
            onChange={(city_id?: Uuid) => setFilters((current) => ({ ...current, city_id }))}
          />
          <Select
            allowClear
            placeholder="Объект"
            className="cr-filter"
            options={referenceData.facilities.map((facility) => ({ label: facility.name, value: facility.id }))}
            onChange={(facility_id?: Uuid) => setFilters((current) => ({ ...current, facility_id }))}
          />
          <Select
            allowClear
            placeholder="Направление"
            className="cr-filter"
            options={referenceData.workTypes.map((workType) => ({ label: getWorkTypeLabel(workType), value: workType.id }))}
            onChange={(work_type_id?: Uuid) => setFilters((current) => ({ ...current, work_type_id }))}
          />
        </div>
      </Card>
      <Section>
        {requests.length === 0 ? (
          <EmptyState title="Заявки не найдены" description="Измените фильтры или создайте новую заявку." />
        ) : (
          <Table<ContractorRequest>
            rowKey="id"
            columns={columns}
            dataSource={requests}
            pagination={{ pageSize: 10, showSizeChanger: true }}
            onRow={(record) => ({
              onDoubleClick: () => navigate(`/applications/contractor-requests/${record.id}`),
            })}
          />
        )}
      </Section>
    </div>
  );
}
