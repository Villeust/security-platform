import { AlertOutlined, CheckCircleOutlined, ClockCircleOutlined, FileDoneOutlined, FileTextOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { List, Space, Typography } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useMemo, useState } from 'react';

import { Button, ErrorState, Loader } from '../../components/design-system';
import { useAuth } from '../../context/AuthContext';
import { ActionCard, AssignmentStatusBadge, ContractorEmptyState, DataTable, MetricCard, PortalPage, RequestStatusBadge, SectionCard } from './components';
import { formatDate } from './constants';
import { getContractorDashboard, getContractorMe, getContractorNotifications, getContractorTasks } from './services';
import type { ContractorDashboard, ContractorMe, ContractorNotification, ContractorTask } from './types';

export function ContractorDashboardPage() {
  const [dashboard, setDashboard] = useState<ContractorDashboard | null>(null);
  const [profile, setProfile] = useState<ContractorMe | null>(null);
  const [tasks, setTasks] = useState<ContractorTask[]>([]);
  const [notifications, setNotifications] = useState<ContractorNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const navigate = useNavigate();
  const auth = useAuth();

  const load = () => {
    setLoading(true);
    setFailed(false);
    Promise.all([getContractorDashboard(), getContractorMe(), getContractorTasks(), getContractorNotifications()])
      .then(([dashboardData, profileData, taskData, notificationData]) => {
        setDashboard(dashboardData);
        setProfile(profileData);
        setTasks(taskData);
        setNotifications(notificationData);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const overdueTasks = useMemo(() => tasks.filter((task) => task.status !== 'COMPLETED' && task.status !== 'CANCELLED'), [tasks]);
  const resultRequired = tasks.filter((task) => task.status === 'IN_PROGRESS').length;
  const company = profile?.contractors.find((item) => item.is_primary)?.name ?? profile?.contractors[0]?.name ?? 'Компания не назначена';
  const currentDate = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'full' }).format(new Date());

  if (loading) return <Loader label="Загрузка главной страницы" />;
  if (failed || !dashboard) {
    return (
      <PortalPage title="Главная" description="Рабочая область подрядчика и контроль выполнения назначенных заявок">
        <ErrorState title="Не удалось загрузить портал" description="Проверьте подключение к backend и повторите попытку." />
        <Button onClick={load}>Повторить</Button>
      </PortalPage>
    );
  }

  return (
    <PortalPage title="Главная" description="Что требует внимания прямо сейчас">
      <section className="contractor-welcome">
        <div>
          <Typography.Title level={3}>Здравствуйте, {auth.currentUser?.display_name ?? profile?.display_name}</Typography.Title>
          <Typography.Text type="secondary">{company} · {currentDate}</Typography.Text>
        </div>
        <div className="contractor-quick-actions">
          <ActionCard title="Открыть заявки" description="Перейти к назначенным работам" icon={<FileTextOutlined />} onClick={() => navigate('/contractor/requests')} />
          <ActionCard title="Открыть задачи" description="Посмотреть текущие действия" icon={<PlayCircleOutlined />} onClick={() => navigate('/contractor/tasks')} />
        </div>
      </section>

      <div className="contractor-metrics-grid">
        <MetricCard title="Активные заявки" value={dashboard.active_requests} description="Назначены вашей компании" icon={<FileTextOutlined />} onClick={() => navigate('/contractor/requests')} />
        <MetricCard title="Ожидают принятия" value={dashboard.assigned_tasks} description="Нужно подтвердить работу" tone="warning" icon={<ClockCircleOutlined />} onClick={() => navigate('/contractor/tasks')} />
        <MetricCard title="В работе" value={dashboard.in_progress_tasks} description="Приняты или выполняются" tone="info" icon={<PlayCircleOutlined />} onClick={() => navigate('/contractor/tasks')} />
        <MetricCard title="Требуют результата" value={resultRequired} description="Загрузите результат работ" tone="warning" icon={<FileDoneOutlined />} onClick={() => navigate('/contractor/tasks')} />
        <MetricCard title="Просрочено" value={overdueTasks.length} description="Проверьте сроки выполнения" tone="danger" icon={<AlertOutlined />} onClick={() => navigate('/contractor/tasks')} />
        <MetricCard title="Завершено" value={dashboard.completed_tasks} description="Работы выполнены" tone="success" icon={<CheckCircleOutlined />} onClick={() => navigate('/contractor/tasks')} />
      </div>

      <div className="contractor-dashboard-grid">
        <SectionCard className="contractor-table-card" title="Последние заявки" description="Недавно обновлённые назначения">
          {dashboard.latest_requests.length ? (
            <DataTable
              rowKey="id"
              dataSource={dashboard.latest_requests}
              pagination={false}
              columns={[
                { title: 'Номер', dataIndex: 'request_number', render: (value, record) => <Link to={`/contractor/requests/${record.id}`}>{value ?? 'Без номера'}</Link> },
                { title: 'Название', dataIndex: 'title' },
                { title: 'Статус', dataIndex: 'status', render: (status) => <RequestStatusBadge status={status} /> },
                { title: 'Назначение', render: (_, record) => record.assignments[0] ? <AssignmentStatusBadge status={record.assignments[0].status} /> : '—' },
                { title: 'Срок', dataIndex: 'desired_completion_date', render: (value) => formatDate(value) },
              ]}
            />
          ) : (
            <ContractorEmptyState title="Нет заявок" description="Для вашей компании пока нет назначенных заявок." actionLabel="Открыть заявки" onAction={() => navigate('/contractor/requests')} />
          )}
        </SectionCard>

        <div className="contractor-stack">
          <SectionCard title="Ближайшие сроки" description="Что может потребовать внимания">
            {tasks.length ? (
              <List
                dataSource={tasks.slice(0, 5)}
                renderItem={(task) => (
                  <List.Item>
                    <List.Item.Meta title="Назначение" description={`Обновлено: ${formatDate(task.updated_at, true)}`} />
                    <AssignmentStatusBadge status={task.status} />
                  </List.Item>
                )}
              />
            ) : <ContractorEmptyState title="Нет задач" description="Активные задачи появятся после назначения заявки." />}
          </SectionCard>
          <SectionCard title="Последние уведомления" description="События по вашим заявкам">
            {notifications.length ? (
              <List dataSource={notifications.slice(0, 4)} renderItem={(item) => <List.Item><List.Item.Meta title={item.title} description={item.message} /></List.Item>} />
            ) : <ContractorEmptyState title="Новых уведомлений нет" description="Здесь появятся важные события по вашим заявкам." />}
          </SectionCard>
        </div>
      </div>
    </PortalPage>
  );
}
