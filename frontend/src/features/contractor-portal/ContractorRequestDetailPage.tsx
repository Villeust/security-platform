import { ArrowLeftOutlined, DownloadOutlined, FileAddOutlined, SendOutlined } from '@ant-design/icons';
import { Alert, Card, Descriptions, Form, Input, List, Space, Steps, Table, Tabs, Timeline, Typography, message } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { Button, Loader } from '../../components/design-system';
import type { ContractorRequest, RequestAttachment, RequestAttachmentCategory, RequestComment, RequestHistoryItem } from '../contractor-requests/types/api';
import { AssignmentStatusBadge, ContractorEmptyState, PortalPage, RequestStatusBadge } from './components';
import { fileCategoryLabel, formatDate, historyEventLabel } from './constants';
import { acceptContractorRequest, createContractorRequestComment, getContractorRequest, getContractorRequestAttachments, getContractorRequestComments, getContractorRequestHistory, updateContractorAssignmentStatus } from './services';

const stepOrder = ['ASSIGNED', 'ACCEPTED', 'IN_PROGRESS', 'COMPLETED'];

export function ContractorRequestDetailPage() {
  const { requestId } = useParams();
  const [request, setRequest] = useState<ContractorRequest | null>(null);
  const [comments, setComments] = useState<RequestComment[]>([]);
  const [attachments, setAttachments] = useState<RequestAttachment[]>([]);
  const [history, setHistory] = useState<RequestHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [commentForm] = Form.useForm<{ body: string }>();
  const navigate = useNavigate();

  const load = () => {
    if (!requestId) return;
    setLoading(true);
    Promise.all([getContractorRequest(requestId), getContractorRequestComments(requestId), getContractorRequestAttachments(requestId), getContractorRequestHistory(requestId)])
      .then(([requestData, commentData, attachmentData, historyData]) => {
        setRequest(requestData);
        setComments(commentData);
        setAttachments(attachmentData);
        setHistory(historyData);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [requestId]);

  if (!requestId) return <Alert type="error" message="Заявка не найдена" />;
  if (!request) return <Loader label="Загрузка заявки" />;

  const assignment = request.assignments[0];
  const activeStep = Math.max(0, stepOrder.indexOf(assignment?.status ?? 'ASSIGNED'));
  const workResults = attachments.filter((item) => item.category === 'WORK_RESULT');

  const accept = async () => {
    setRequest(await acceptContractorRequest(requestId));
    message.success('Назначение принято');
    load();
  };

  const setAssignmentStatus = async (status: string) => {
    if (!assignment) return;
    await updateContractorAssignmentStatus(assignment.id, status);
    message.success('Статус обновлён');
    load();
  };

  const submitComment = async () => {
    const values = await commentForm.validateFields();
    await createContractorRequestComment(requestId, values.body);
    commentForm.resetFields();
    message.success('Комментарий добавлен');
    load();
  };

  return (
    <PortalPage
      title={request.request_number ?? 'Заявка без номера'}
      description={request.title}
      actions={<Space wrap><Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/contractor/requests')}>К списку</Button>{assignment?.status === 'ASSIGNED' ? <Button type="primary" loading={loading} onClick={accept}>Принять</Button> : null}</Space>}
    >
      <Card className="contractor-card">
        <Space wrap>
          <RequestStatusBadge status={request.status} />
          {assignment ? <AssignmentStatusBadge status={assignment.status} /> : null}
          <Typography.Text type="secondary">Срок: {formatDate(request.desired_completion_date)}</Typography.Text>
        </Space>
      </Card>

      <Tabs
        items={[
          {
            key: 'info',
            label: 'Основная информация',
            children: (
              <Card className="contractor-card">
                <Descriptions column={{ xs: 1, md: 2 }}>
                  <Descriptions.Item label="Название">{request.title}</Descriptions.Item>
                  <Descriptions.Item label="Приоритет">{request.priority ?? '—'}</Descriptions.Item>
                  <Descriptions.Item label="Описание">{request.description ?? '—'}</Descriptions.Item>
                  <Descriptions.Item label="Контакт">{[request.contact_name, request.contact_email, request.contact_phone].filter(Boolean).join(', ') || '—'}</Descriptions.Item>
                  <Descriptions.Item label="Создана">{formatDate(request.created_at, true)}</Descriptions.Item>
                  <Descriptions.Item label="Обновлена">{formatDate(request.updated_at, true)}</Descriptions.Item>
                </Descriptions>
              </Card>
            ),
          },
          {
            key: 'assignment',
            label: 'Моё назначение',
            children: (
              <Card className="contractor-card">
                {assignment ? (
                  <Space direction="vertical" size="large" className="cr-collaboration-stack">
                    <Steps current={activeStep} items={['Назначено', 'Принято', 'В работе', 'Выполнено'].map((title) => ({ title }))} />
                    <Descriptions column={{ xs: 1, md: 3 }}>
                      <Descriptions.Item label="Направление">{assignment.work_type_id}</Descriptions.Item>
                      <Descriptions.Item label="Статус"><AssignmentStatusBadge status={assignment.status} /></Descriptions.Item>
                      <Descriptions.Item label="Дата назначения">{formatDate(assignment.assigned_at, true)}</Descriptions.Item>
                    </Descriptions>
                    <div className="contractor-actions">
                      {assignment.status === 'ASSIGNED' ? <Button type="primary" onClick={accept}>Принять</Button> : null}
                      {assignment.status === 'ACCEPTED' ? <Button onClick={() => void setAssignmentStatus('IN_PROGRESS')}>Начать работу</Button> : null}
                      {assignment.status === 'IN_PROGRESS' ? <Button icon={<FileAddOutlined />}>Загрузить результат</Button> : null}
                      {assignment.status === 'IN_PROGRESS' ? <Button type="primary" onClick={() => void setAssignmentStatus('COMPLETED')}>Завершить</Button> : null}
                    </div>
                  </Space>
                ) : <ContractorEmptyState title="Нет назначения" description="Ваша компания не имеет активного назначения по этой заявке." />}
              </Card>
            ),
          },
          {
            key: 'comments',
            label: 'Комментарии',
            children: (
              <Card className="contractor-card">
                <Space direction="vertical" size="large" className="cr-collaboration-stack">
                  {comments.length ? comments.map((comment) => (
                    <div className="contractor-comment" key={comment.id}>
                      <Space direction="vertical">
                        <Typography.Text strong>{comment.author_type === 'CONTRACTOR_USER' ? 'Подрядчик' : 'Security Platform'}</Typography.Text>
                        <Typography.Text>{comment.body}</Typography.Text>
                        <Typography.Text type="secondary">{formatDate(comment.created_at, true)}{comment.is_edited ? ' · изменено' : ''}</Typography.Text>
                      </Space>
                    </div>
                  )) : <ContractorEmptyState title="Нет комментариев" description="Обсуждение по заявке пока не начато." />}
                  <Form form={commentForm} layout="vertical">
                    <Form.Item name="body" rules={[{ required: true, message: 'Введите комментарий' }]}>
                      <Input.TextArea rows={3} placeholder="Напишите комментарий" />
                    </Form.Item>
                    <Button type="primary" icon={<SendOutlined />} onClick={() => void submitComment()}>Отправить</Button>
                  </Form>
                </Space>
              </Card>
            ),
          },
          {
            key: 'attachments',
            label: 'Вложения',
            children: (
              <Card className="contractor-card contractor-table-card">
                {attachments.length ? (
                  <Table rowKey="id" dataSource={attachments} pagination={false} scroll={{ x: 760 }} columns={[
                    { title: 'Файл', dataIndex: 'original_filename' },
                    { title: 'Категория', dataIndex: 'category', render: (value: RequestAttachmentCategory) => fileCategoryLabel[value] ?? value },
                    { title: 'Размер', dataIndex: 'size_bytes', render: (value) => `${Math.ceil(value / 1024)} КБ` },
                    { title: 'Дата', dataIndex: 'created_at', render: (value) => formatDate(value, true) },
                    { title: 'Действие', render: () => <Button icon={<DownloadOutlined />}>Скачать</Button> },
                  ]} />
                ) : <ContractorEmptyState title="Нет вложений" description="Общие файлы по заявке пока не загружены." />}
              </Card>
            ),
          },
          {
            key: 'results',
            label: 'Результаты работ',
            children: (
              <Card className="contractor-card contractor-table-card">
                {workResults.length ? (
                  <Table rowKey="id" dataSource={workResults} pagination={false} columns={[
                    { title: 'Результат', dataIndex: 'original_filename' },
                    { title: 'Дата', dataIndex: 'created_at', render: (value) => formatDate(value, true) },
                    { title: 'Статус проверки', render: () => 'Ожидает проверки' },
                  ]} />
                ) : <ContractorEmptyState title="Нет результатов работ" description="Перед завершением задачи загрузите результат работ." actionLabel="Загрузить результат" onAction={() => undefined} />}
              </Card>
            ),
          },
          {
            key: 'history',
            label: 'История',
            children: (
              <Card className="contractor-card">
                {history.length ? (
                  <Timeline items={history.map((item) => ({ children: <Space direction="vertical"><Typography.Text strong>{historyEventLabel[item.event_type]}</Typography.Text><Typography.Text type="secondary">{formatDate(item.created_at, true)}</Typography.Text></Space> }))} />
                ) : <ContractorEmptyState title="Нет истории" description="История появится после действий по заявке." />}
              </Card>
            ),
          },
        ]}
      />
    </PortalPage>
  );
}
