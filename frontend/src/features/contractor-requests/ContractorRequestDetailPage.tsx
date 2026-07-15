import { ArrowLeftOutlined, SendOutlined } from '@ant-design/icons';
import { Descriptions, Space, Tag, Timeline, message } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { Button, Card, ErrorState, Loader, PageHeader, Section, Table } from '../../components/design-system';
import { RequestStatusBadge } from './components/RequestStatusBadge';
import { useReferenceData } from './hooks/useReferenceData';
import { getRequest } from './services/requestService';
import type { ContractorRequest, RequestAssignment } from './types/api';
import { contractorName, facilityName, formatDate, getWorkTypeLabel, labelsByIds } from './utils';

export function ContractorRequestDetailPage() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const referenceData = useReferenceData();
  const [request, setRequest] = useState<ContractorRequest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!requestId) {
      setError('Не указан идентификатор заявки.');
      setIsLoading(false);
      return;
    }
    getRequest(requestId)
      .then((data) => {
        setRequest(data);
        setError(null);
      })
      .catch((requestError: unknown) => {
        console.error('Failed to load request details', requestError);
        setError('Не удалось загрузить карточку заявки.');
      })
      .finally(() => setIsLoading(false));
  }, [requestId]);

  if (isLoading || referenceData.isLoading) {
    return <Loader label="Загрузка карточки" />;
  }

  if (error || referenceData.error || !request) {
    return <ErrorState title="Карточка недоступна" description={error ?? referenceData.error ?? undefined} />;
  }

  const assignmentColumns = [
    {
      title: 'Направление',
      key: 'work_type',
      render: (_value: unknown, assignment: RequestAssignment) => getWorkTypeLabel(referenceData.workTypes.find((workType) => workType.id === assignment.work_type_id)),
    },
    {
      title: 'Подрядчик',
      key: 'contractor',
      render: (_value: unknown, assignment: RequestAssignment) => contractorName(assignment.contractor_id, referenceData.contractors),
    },
    { title: 'Статус', dataIndex: 'status', key: 'status', render: (status: RequestAssignment['status']) => <RequestStatusBadge status={status} /> },
    { title: 'Назначено', dataIndex: 'assigned_at', key: 'assigned_at', render: (value: string) => formatDate(value) },
    { title: 'Принято', dataIndex: 'accepted_at', key: 'accepted_at', render: (value: string | null) => formatDate(value) },
    { title: 'Завершено', dataIndex: 'completed_at', key: 'completed_at', render: (value: string | null) => formatDate(value) },
  ];

  return (
    <div className="sp-page">
      <PageHeader
        title={request.request_number ?? request.id}
        description={request.title}
        actions={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/applications/contractor-requests')}>
              Назад
            </Button>
            <Button
              icon={<SendOutlined />}
              disabled
              onClick={() => message.info('Backend API публикации DRAFT пока отсутствует.')}
            >
              Опубликовать
            </Button>
          </Space>
        }
      />
      <Section title="Основная информация">
        <Card>
          <Descriptions bordered column={2}>
            <Descriptions.Item label="Статус">
              <RequestStatusBadge status={request.status} />
            </Descriptions.Item>
            <Descriptions.Item label="Приоритет">—</Descriptions.Item>
            <Descriptions.Item label="Город">{referenceData.cities.find((city) => city.id === request.city_id)?.name ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Объект">{facilityName(request.facility_id, referenceData.facilities)}</Descriptions.Item>
            <Descriptions.Item label="Помещение">{referenceData.premises.find((premise) => premise.id === request.premise_id)?.name ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Желаемый срок">—</Descriptions.Item>
            <Descriptions.Item label="Направления">
              <Space wrap>
                {labelsByIds(request.work_type_ids, referenceData.workTypes, getWorkTypeLabel).map((label) => (
                  <Tag key={label}>{label}</Tag>
                ))}
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Дата создания">{formatDate(request.created_at)}</Descriptions.Item>
            <Descriptions.Item label="Контакт">{request.contact_name ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Email">{request.contact_email ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Телефон">{request.contact_phone ?? '—'}</Descriptions.Item>
            <Descriptions.Item label="Описание">{request.description ?? '—'}</Descriptions.Item>
          </Descriptions>
        </Card>
      </Section>
      <Section title="Назначения подрядчиков">
        <Table<RequestAssignment> rowKey="id" columns={assignmentColumns} dataSource={request.assignments} />
      </Section>
      <Section title="История изменений">
        <Card>
          <Timeline
            items={[
              {
                children: `Заявка создана: ${formatDate(request.created_at)}`,
              },
              ...request.assignments.map((assignment) => ({
                children: `Назначение ${assignment.status}: ${formatDate(assignment.updated_at)}`,
              })),
            ]}
          />
        </Card>
      </Section>
    </div>
  );
}
