import { ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined, PlayCircleOutlined, SendOutlined, UndoOutlined } from '@ant-design/icons';
import { Descriptions, Space, Tabs, Tag, Timeline, message } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { Button, Card, ErrorState, Loader, PageHeader, Section, Table } from '../../components/design-system';
import { AssignmentWorkResults } from './components/AssignmentWorkResults';
import { RequestAttachments } from './components/RequestAttachments';
import { RequestComments } from './components/RequestComments';
import { RequestStatusBadge } from './components/RequestStatusBadge';
import { useReferenceData } from './hooks/useReferenceData';
import { getRequest, getRequestHistory, publishRequest, updateRequestStatus } from './services/requestService';
import type { ContractorRequest, RequestAssignment, RequestHistoryItem, RequestStatus } from './types/api';
import { contractorName, facilityName, formatDate, getWorkTypeLabel, labelsByIds } from './utils';

const statusActions: Partial<Record<RequestStatus, Array<{ status: RequestStatus; label: string; icon: JSX.Element }>>> = {
  NEW: [
    { status: 'PARTIALLY_ASSIGNED', label: 'Частично назначена', icon: <SendOutlined /> },
    { status: 'ASSIGNED', label: 'Назначена', icon: <SendOutlined /> },
    { status: 'CANCELLED', label: 'Отменить', icon: <CloseCircleOutlined /> },
  ],
  PARTIALLY_ASSIGNED: [
    { status: 'ASSIGNED', label: 'Назначена', icon: <SendOutlined /> },
    { status: 'IN_PROGRESS', label: 'В работу', icon: <PlayCircleOutlined /> },
    { status: 'CANCELLED', label: 'Отменить', icon: <CloseCircleOutlined /> },
  ],
  ASSIGNED: [
    { status: 'IN_PROGRESS', label: 'В работу', icon: <PlayCircleOutlined /> },
    { status: 'CANCELLED', label: 'Отменить', icon: <CloseCircleOutlined /> },
  ],
  IN_PROGRESS: [
    { status: 'COMPLETED', label: 'Завершить', icon: <CheckCircleOutlined /> },
    { status: 'CANCELLED', label: 'Отменить', icon: <CloseCircleOutlined /> },
  ],
  COMPLETED: [
    { status: 'CLOSED', label: 'Закрыть', icon: <CheckCircleOutlined /> },
    { status: 'IN_PROGRESS', label: 'Вернуть в работу', icon: <UndoOutlined /> },
  ],
};

export function ContractorRequestDetailPage() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const referenceData = useReferenceData();
  const [request, setRequest] = useState<ContractorRequest | null>(null);
  const [history, setHistory] = useState<RequestHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!requestId) {
      setError('Не указан идентификатор заявки.');
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const [requestData, historyData] = await Promise.all([getRequest(requestId), getRequestHistory(requestId)]);
      setRequest(requestData);
      setHistory(historyData);
      setError(null);
    } catch (requestError: unknown) {
      console.error('Failed to load request details', requestError);
      setError('Не удалось загрузить карточку заявки.');
    } finally {
      setIsLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    void load();
  }, [load]);

  const actions = useMemo(() => (request ? statusActions[request.status] ?? [] : []), [request]);

  async function refreshCollaboration() {
    if (!request) {
      return;
    }
    setHistory(await getRequestHistory(request.id));
  }

  async function publish() {
    if (!request) {
      return;
    }
    try {
      const updated = await publishRequest(request.id);
      setRequest(updated);
      setHistory(await getRequestHistory(updated.id));
      message.success('Заявка опубликована.');
    } catch (actionError) {
      console.error('Failed to publish request', actionError);
      message.error('Не удалось опубликовать заявку.');
    }
  }

  async function changeStatus(status: RequestStatus) {
    if (!request) {
      return;
    }
    try {
      const updated = await updateRequestStatus(request.id, status);
      setRequest(updated);
      setHistory(await getRequestHistory(updated.id));
      message.success('Статус обновлен.');
    } catch (actionError) {
      console.error('Failed to update request status', actionError);
      message.error('Не удалось обновить статус.');
    }
  }

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
          <Space wrap>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/applications/contractor-requests')}>
              Назад
            </Button>
            {request.status === 'DRAFT' && (
              <Button type="primary" icon={<SendOutlined />} onClick={publish}>
                Опубликовать
              </Button>
            )}
            {actions.map((action) => (
              <Button key={action.status} icon={action.icon} onClick={() => changeStatus(action.status)} danger={action.status === 'CANCELLED'}>
                {action.label}
              </Button>
            ))}
          </Space>
        }
      />
      <Tabs
        items={[
          {
            key: 'main',
            label: 'Основная информация',
            children: (
              <Section>
                <Card>
                  <Descriptions bordered column={2}>
                    <Descriptions.Item label="Статус">
                      <RequestStatusBadge status={request.status} />
                    </Descriptions.Item>
                    <Descriptions.Item label="Приоритет">{request.priority ?? '—'}</Descriptions.Item>
                    <Descriptions.Item label="Город">{referenceData.cities.find((city) => city.id === request.city_id)?.name ?? '—'}</Descriptions.Item>
                    <Descriptions.Item label="Объект">{request.facility_id ? facilityName(request.facility_id, referenceData.facilities) : '—'}</Descriptions.Item>
                    <Descriptions.Item label="Помещение">{referenceData.premises.find((premise) => premise.id === request.premise_id)?.name ?? '—'}</Descriptions.Item>
                    <Descriptions.Item label="Желаемый срок">{formatDate(request.desired_completion_date)}</Descriptions.Item>
                    <Descriptions.Item label="Направления">
                      <Space wrap>
                        {labelsByIds(request.work_type_ids, referenceData.workTypes, getWorkTypeLabel).map((label) => (
                          <Tag key={label}>{label}</Tag>
                        ))}
                      </Space>
                    </Descriptions.Item>
                    <Descriptions.Item label="Дата создания">{formatDate(request.created_at)}</Descriptions.Item>
                    <Descriptions.Item label="Завершено">{formatDate(request.completed_at)}</Descriptions.Item>
                    <Descriptions.Item label="Закрыто">{formatDate(request.closed_at)}</Descriptions.Item>
                    <Descriptions.Item label="Контакт">{request.contact_name ?? '—'}</Descriptions.Item>
                    <Descriptions.Item label="Email">{request.contact_email ?? '—'}</Descriptions.Item>
                    <Descriptions.Item label="Телефон">{request.contact_phone ?? '—'}</Descriptions.Item>
                    <Descriptions.Item label="Описание">{request.description ?? '—'}</Descriptions.Item>
                  </Descriptions>
                </Card>
              </Section>
            ),
          },
          {
            key: 'execution',
            label: 'Исполнение',
            children: (
              <Section>
                <Table<RequestAssignment> rowKey="id" columns={assignmentColumns} dataSource={request.assignments} />
                <AssignmentWorkResults requestId={request.id} assignments={request.assignments} contractors={referenceData.contractors} workTypes={referenceData.workTypes} mode="internal" />
              </Section>
            ),
          },
          {
            key: 'comments',
            label: 'Комментарии',
            children: <RequestComments requestId={request.id} mode="internal" />,
          },
          {
            key: 'attachments',
            label: 'Вложения',
            children: <RequestAttachments requestId={request.id} mode="internal" />,
          },
          {
            key: 'history',
            label: 'История',
            children: (
              <Section>
                <Card>
                  <Timeline
                    items={history.map((item) => ({
                      children: (
                        <Space direction="vertical" size={2}>
                          <span>
                            {item.event_type}
                            {item.old_status || item.new_status ? `: ${item.old_status ?? '—'} → ${item.new_status ?? '—'}` : ''}
                          </span>
                          <span>{formatDate(item.created_at)}</span>
                          {item.comment && <span>{item.comment}</span>}
                        </Space>
                      ),
                    }))}
                  />
                  <Button onClick={refreshCollaboration}>Обновить историю</Button>
                </Card>
              </Section>
            ),
          },
        ]}
      />
    </div>
  );
}
