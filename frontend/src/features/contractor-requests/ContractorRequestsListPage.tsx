import { AppstoreOutlined, PlusOutlined } from '@ant-design/icons';
import { Select, Space, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Button, Card, EmptyState, ErrorState, Loader, PageHeader, SearchBar, Section, Table } from '../../components/design-system';
import { RequestStatusBadge } from './components/RequestStatusBadge';
import { useReferenceData } from './hooks/useReferenceData';
import { useRequests } from './hooks/useRequests';
import type { ContractorRequest, RequestStatus, Uuid } from './types/api';
import { contractorName, facilityName, formatDate, getWorkTypeLabel, labelsByIds } from './utils';

type Filters = {
  status?: RequestStatus;
  priority?: string;
  cityId?: Uuid;
  facilityId?: Uuid;
  workTypeId?: Uuid;
};

export function ContractorRequestsListPage() {
  const navigate = useNavigate();
  const { requests, isLoading, error } = useRequests();
  const referenceData = useReferenceData();
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Filters>({});

  const filteredRequests = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('ru-RU');
    return requests
      .filter((request) => {
        const text = [request.request_number, request.title, request.description].filter(Boolean).join(' ').toLocaleLowerCase('ru-RU');
        const matchesSearch = !query || text.includes(query);
        const matchesStatus = !filters.status || request.status === filters.status;
        const matchesCity = !filters.cityId || request.city_id === filters.cityId;
        const matchesFacility = !filters.facilityId || request.facility_id === filters.facilityId;
        const matchesWorkType = !filters.workTypeId || request.work_type_ids.includes(filters.workTypeId);
        return matchesSearch && matchesStatus && matchesCity && matchesFacility && matchesWorkType;
      })
      .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  }, [filters, requests, search]);

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
      render: (_value, record) => facilityName(record.facility_id, referenceData.facilities),
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
    { title: 'Приоритет', key: 'priority', render: () => '—' },
    { title: 'Статус', dataIndex: 'status', key: 'status', render: (status: RequestStatus) => <RequestStatusBadge status={status} /> },
    { title: 'Желаемый срок', key: 'desired_completion_date', render: () => '—' },
    {
      title: 'Дата создания',
      dataIndex: 'created_at',
      key: 'created_at',
      sorter: (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
      defaultSortOrder: 'descend',
      render: (value: string) => formatDate(value),
    },
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
        description="Создание и просмотр заявок на работы подрядчиков."
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/applications/contractor-requests/new')}>
            Создать заявку
          </Button>
        }
      />
      <Card>
        <div className="cr-toolbar">
          <SearchBar placeholder="Поиск по номеру, заголовку или описанию" onSearch={setSearch} />
          <Select
            allowClear
            placeholder="Статус"
            className="cr-filter"
            options={[
              { label: 'NEW', value: 'NEW' },
              { label: 'ASSIGNED', value: 'ASSIGNED' },
            ]}
            onChange={(status?: RequestStatus) => setFilters((current) => ({ ...current, status }))}
          />
          <Select allowClear disabled placeholder="Приоритет" className="cr-filter" onChange={(priority?: string) => setFilters((current) => ({ ...current, priority }))} />
          <Select
            allowClear
            placeholder="Город"
            className="cr-filter"
            options={referenceData.cities.map((city) => ({ label: city.name, value: city.id }))}
            onChange={(cityId?: Uuid) => setFilters((current) => ({ ...current, cityId }))}
          />
          <Select
            allowClear
            placeholder="Объект"
            className="cr-filter"
            options={referenceData.facilities.map((facility) => ({ label: facility.name, value: facility.id }))}
            onChange={(facilityId?: Uuid) => setFilters((current) => ({ ...current, facilityId }))}
          />
          <Select
            allowClear
            placeholder="Направление"
            className="cr-filter"
            options={referenceData.workTypes.map((workType) => ({ label: getWorkTypeLabel(workType), value: workType.id }))}
            onChange={(workTypeId?: Uuid) => setFilters((current) => ({ ...current, workTypeId }))}
          />
        </div>
      </Card>
      <Section>
        {filteredRequests.length === 0 ? (
          <EmptyState title="Заявки не найдены" description="Измените фильтры или создайте новую заявку." />
        ) : (
          <Table<ContractorRequest>
            rowKey="id"
            columns={columns}
            dataSource={filteredRequests}
            pagination={{ pageSize: 10, showSizeChanger: true }}
            onRow={(record) => ({
              onDoubleClick: () => navigate(`/applications/contractor-requests/${record.id}`),
            })}
          />
        )}
      </Section>
      <div className="cr-api-note">
        <AppstoreOutlined /> Приоритет и желаемый срок пока не возвращаются backend API.
      </div>
    </div>
  );
}
