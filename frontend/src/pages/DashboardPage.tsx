import {
  ApartmentOutlined,
  BellOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FileDoneOutlined,
  FileSearchOutlined,
  PlusOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined,
  UserAddOutlined,
} from '@ant-design/icons';
import { Alert, Button, Space, Tabs, Typography, type TabsProps } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'react-router-dom';

import {
  ActivityTimeline,
  AttentionCard,
  ChartCard,
  CompactDataTable,
  CompactEmptyState,
  DashboardPageHeader,
  DashboardSection,
  MetricCard,
  PeriodSelector,
  SectionCard,
  SkeletonGrid,
  StatusPill,
  type DashboardTone,
} from '../components/design-system';
import { useAuth } from '../context/AuthContext';
import { formatDate, priorityLabel, relativeDeadline, requestStatusLabel, roleLabel, serviceStatusLabel } from '../features/dashboard/constants';
import { getDashboard } from '../features/dashboard/service';
import type {
  DashboardContractorSummaryItem,
  DashboardDeadlineItem,
  DashboardPeriodKey,
  DashboardRequestItem,
  DashboardResponse,
  DashboardServiceStatusItem,
} from '../features/dashboard/types';

const requestGroupLabels: Record<string, string> = {
  new: 'Новые',
  unassigned: 'Без назначения',
  awaiting_acceptance: 'Ожидают принятия',
  in_progress: 'В работе',
  overdue: 'Просроченные',
  recently_completed: 'Недавно завершённые',
};

const metricIcon: Record<string, JSX.Element> = {
  active_requests: <FileSearchOutlined />,
  new_requests: <PlusOutlined />,
  in_progress_requests: <ClockCircleOutlined />,
  overdue_requests: <ExclamationCircleOutlined />,
  completed_period: <FileDoneOutlined />,
  active_contractors: <TeamOutlined />,
  awaiting_acceptance: <BellOutlined />,
  average_completion_hours: <CheckCircleOutlined />,
};

const metricTone: Record<string, DashboardTone> = {
  active_requests: 'info',
  new_requests: 'info',
  in_progress_requests: 'warning',
  overdue_requests: 'critical',
  completed_period: 'success',
  active_contractors: 'info',
  awaiting_acceptance: 'high',
  average_completion_hours: 'neutral',
};

const metricDescription: Record<string, string> = {
  active_requests: 'Новые, назначенные и находящиеся в работе заявки',
  new_requests: 'Заявки, ожидающие первичной обработки',
  in_progress_requests: 'Работы, которые сейчас выполняются подрядчиками',
  overdue_requests: 'Заявки с истёкшим желаемым сроком выполнения',
  completed_period: 'Завершённые заявки за выбранный период',
  active_contractors: 'Компании, доступные для назначения работ',
  awaiting_acceptance: 'Назначения, которые подрядчики ещё не приняли',
  average_completion_hours: 'Операционная оценка по накопленным данным выполнения',
};

const statusTone: Record<string, DashboardTone> = {
  NEW: 'info',
  ASSIGNED: 'info',
  PARTIALLY_ASSIGNED: 'warning',
  IN_PROGRESS: 'warning',
  COMPLETED: 'success',
  CLOSED: 'neutral',
  CANCELLED: 'critical',
  LOW: 'neutral',
  MEDIUM: 'info',
  HIGH: 'high',
  CRITICAL: 'critical',
  works: 'success',
  configured: 'success',
  not_configured: 'warning',
  limited: 'warning',
  unavailable: 'critical',
  planned: 'neutral',
};

function requestTarget(params: Record<string, string>) {
  return `/applications/contractor-requests?${new URLSearchParams(params).toString()}`;
}

function normalizeTone(value?: string | null): DashboardTone {
  if (value === 'critical' || value === 'high' || value === 'warning' || value === 'success' || value === 'neutral') {
    return value;
  }
  return 'info';
}

function metricTarget(key: string) {
  const map: Record<string, string> = {
    active_requests: requestTarget({ status: 'active' }),
    new_requests: requestTarget({ status: 'NEW' }),
    in_progress_requests: requestTarget({ status: 'IN_PROGRESS' }),
    overdue_requests: requestTarget({ overdue: 'true' }),
    completed_period: requestTarget({ status: 'COMPLETED' }),
    awaiting_acceptance: requestTarget({ assignment_status: 'ASSIGNED' }),
  };
  return map[key] ?? '/applications/contractor-requests';
}

function titleForRequest(record: DashboardRequestItem) {
  return record.request_number ? `${record.request_number} · ${record.title}` : record.title;
}

export function DashboardPage() {
  const [period, setPeriod] = useState<DashboardPeriodKey>('7d');
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeRequestGroup, setActiveRequestGroup] = useState('new');
  const navigate = useNavigate();
  const auth = useAuth();

  const loadDashboard = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const next = await getDashboard(period, signal);
        setData(next);
        if (!next.request_groups[activeRequestGroup]) {
          setActiveRequestGroup(Object.keys(next.request_groups)[0] ?? 'new');
        }
      } catch (caught) {
        if (signal?.aborted) return;
        console.error('Dashboard loading failed', caught);
        setError('Не удалось загрузить данные центра управления. Проверьте доступность backend и повторите попытку.');
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [activeRequestGroup, period],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadDashboard(controller.signal);
    return () => controller.abort();
  }, [loadDashboard]);

  const requestColumns = useMemo<ColumnsType<DashboardRequestItem>>(
    () => [
      {
        title: 'Номер',
        dataIndex: 'request_number',
        key: 'request_number',
        fixed: 'left',
        render: (_, record) => (
            <Button type="link" className="ops-link-button" onClick={() => navigate(`/applications/contractor-requests/${record.id}`)}>
            {record.request_number ?? 'Без номера'}
          </Button>
        ),
      },
      { title: 'Название', dataIndex: 'title', key: 'title', ellipsis: true, render: (_, record) => <Typography.Text title={titleForRequest(record)}>{record.title}</Typography.Text> },
      { title: 'Объект', dataIndex: 'facility', key: 'facility', render: (value) => value ?? '—' },
      { title: 'Город', dataIndex: 'city', key: 'city', render: (value) => value ?? '—' },
      { title: 'Направления', dataIndex: 'work_types', key: 'work_types', render: (value: string[]) => value.length ? value.join(', ') : '—' },
      { title: 'Подрядчик', dataIndex: 'contractor', key: 'contractor', render: (value) => value ?? 'Не назначен' },
      { title: 'Статус', dataIndex: 'status', key: 'status', render: (value: string) => <StatusPill label={requestStatusLabel[value] ?? value} tone={statusTone[value] ?? 'neutral'} /> },
      { title: 'Приоритет', dataIndex: 'priority', key: 'priority', render: (value: string | null) => <StatusPill label={value ? priorityLabel[value] ?? value : 'Не задан'} tone={value ? statusTone[value] ?? 'neutral' : 'neutral'} /> },
      { title: 'Срок', dataIndex: 'desired_completion_date', key: 'desired_completion_date', render: (value: string | null) => value ? relativeDeadline(value) : '—' },
      { title: 'Изменено', dataIndex: 'updated_at', key: 'updated_at', render: (value: string) => formatDate(value, true) },
    ],
    [navigate],
  );

  const contractorColumns = useMemo<ColumnsType<DashboardContractorSummaryItem>>(
    () => [
      { title: 'Компания', dataIndex: 'company', key: 'company', ellipsis: true },
      { title: 'Активные', dataIndex: 'active_assignments', key: 'active_assignments', align: 'right' },
      { title: 'В работе', dataIndex: 'in_progress', key: 'in_progress', align: 'right' },
      { title: 'Ожидают', dataIndex: 'awaiting_acceptance', key: 'awaiting_acceptance', align: 'right' },
      { title: 'Просрочено', dataIndex: 'overdue', key: 'overdue', align: 'right' },
      { title: 'Выполнено', dataIndex: 'completed', key: 'completed', align: 'right' },
      {
        title: 'Среднее время',
        dataIndex: 'average_completion_hours',
        key: 'average_completion_hours',
        render: (value: number | null) => (value === null ? 'Недостаточно данных' : `${Math.round(value)} ч`),
      },
      { title: 'Статус', dataIndex: 'status', key: 'status', render: (value: string) => <StatusPill label={value === 'active' ? 'Активен' : 'Неактивен'} tone={value === 'active' ? 'success' : 'neutral'} /> },
    ],
    [],
  );

  const deadlineColumns = useMemo<ColumnsType<DashboardDeadlineItem>>(
    () => [
      {
        title: 'Заявка',
        dataIndex: 'request_number',
        key: 'request_number',
        render: (_, record) => (
            <Button type="link" className="ops-link-button" onClick={() => navigate(`/applications/contractor-requests/${record.request_id}`)}>
            {record.request_number ?? record.title}
          </Button>
        ),
      },
      { title: 'Объект', dataIndex: 'facility', key: 'facility', render: (value) => value ?? '—' },
      { title: 'Подрядчик', dataIndex: 'contractor', key: 'contractor', render: (value) => value ?? 'Не назначен' },
      { title: 'Срок', dataIndex: 'desired_completion_date', key: 'desired_completion_date', render: (value: string, record) => <StatusPill label={relativeDeadline(value)} tone={normalizeTone(record.severity)} /> },
    ],
    [navigate],
  );

  const serviceColumns = useMemo<ColumnsType<DashboardServiceStatusItem>>(
    () => [
      { title: 'Сервис', dataIndex: 'label', key: 'label' },
      { title: 'Статус', dataIndex: 'status', key: 'status', render: (value: string) => <StatusPill label={serviceStatusLabel[value] ?? value} tone={statusTone[value] ?? 'neutral'} /> },
      { title: 'Описание', dataIndex: 'description', key: 'description' },
      { title: 'Проверка', dataIndex: 'last_check', key: 'last_check', render: (value: string | null) => formatDate(value, true) },
    ],
    [],
  );

  const requestTabs = useMemo<TabsProps['items']>(() => {
    const groups = data?.request_groups ?? {};
    return Object.entries(requestGroupLabels).map(([key, label]) => ({
      key,
      label: `${label} (${groups[key]?.length ?? 0})`,
      children: groups[key]?.length ? (
        <CompactDataTable<DashboardRequestItem> rowKey="id" columns={requestColumns} dataSource={groups[key]} />
      ) : (
        <CompactEmptyState title="Активных записей нет" description="Для выбранной категории нет заявок." />
      ),
    }));
  }, [data?.request_groups, requestColumns]);

  const quickActions = [
    { key: 'create-request', label: 'Создать заявку', description: 'Оформить новую заявку подрядчикам', icon: <PlusOutlined />, target: '/applications/contractor-requests/new', permission: 'requests.create' },
    { key: 'overdue', label: 'Открыть просроченные', description: 'Перейти к заявкам со срывом срока', icon: <ClockCircleOutlined />, target: requestTarget({ overdue: 'true' }), permission: 'requests.view' },
    { key: 'contractor', label: 'Добавить подрядчика', description: 'Открыть управление подрядчиками', icon: <TeamOutlined />, target: '/admin/contractors', permission: 'admin.contractors.manage' },
    { key: 'user', label: 'Создать пользователя', description: 'Открыть управление пользователями', icon: <UserAddOutlined />, target: '/admin/users', permission: 'admin.users.manage' },
    { key: 'connections', label: 'Настроить подключение', description: 'LDAP, ADFS, SMTP и интеграции', icon: <SettingOutlined />, target: '/admin/connections', permission: 'admin.connections.manage' },
    { key: 'audit', label: 'Открыть журнал аудита', description: 'Проверить административные события', icon: <SafetyCertificateOutlined />, target: '/admin/audit', permission: 'admin.audit.view' },
  ].filter((action) => auth.hasPermission(action.permission));

  const role = auth.currentUser?.role_codes.find((code) => roleLabel[code]) ?? auth.currentUser?.role_codes[0];
  const currentDate = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'full' }).format(new Date());

  if (loading && !data) {
    return (
      <div className="ops-page">
        <DashboardPageHeader
          title="Центр управления безопасностью"
          subtitle="Оперативный контроль заявок, подрядчиков и сервисов Security Platform"
          userName={auth.currentUser?.display_name}
          userRole={role ? roleLabel[role] ?? role : undefined}
          date={currentDate}
          loading
        >
          <PeriodSelector value={period} onChange={(value) => setPeriod(value as DashboardPeriodKey)} />
        </DashboardPageHeader>
        <SkeletonGrid count={8} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="ops-page">
        <DashboardPageHeader
          title="Центр управления безопасностью"
          subtitle="Оперативный контроль заявок, подрядчиков и сервисов Security Platform"
          userName={auth.currentUser?.display_name}
          userRole={role ? roleLabel[role] ?? role : undefined}
          date={currentDate}
          onRefresh={() => void loadDashboard()}
        />
        <Alert type="error" showIcon message="Не удалось загрузить данные" description={error} action={<Button onClick={() => void loadDashboard()}>Повторить</Button>} />
      </div>
    );
  }

  return (
    <div className="ops-page">
      <DashboardPageHeader
        title="Центр управления безопасностью"
        subtitle="Оперативный контроль заявок, подрядчиков и сервисов Security Platform"
        userName={auth.currentUser?.display_name}
        userRole={role ? roleLabel[role] ?? role : undefined}
        date={currentDate}
        lastRefresh={data ? formatDate(data.generated_at, true) : undefined}
        loading={loading}
        onRefresh={() => void loadDashboard()}
      >
        <PeriodSelector value={period} onChange={(value) => setPeriod(value as DashboardPeriodKey)} />
      </DashboardPageHeader>

      {error ? <Alert type="warning" showIcon message="Данные могут быть неактуальны" description={error} action={<Button onClick={() => void loadDashboard()}>Повторить</Button>} /> : null}

      <DashboardSection title="Требует внимания" description="События, которые стоит обработать в первую очередь.">
        {data?.attention.length ? (
          <div className="ops-attention-grid">
            {data.attention.map((item) => (
              <AttentionCard
                key={item.key}
                label={item.label}
                count={item.count}
                description={item.description}
                severity={normalizeTone(item.severity)}
                onClick={() => navigate(item.target)}
              />
            ))}
          </div>
        ) : (
          <SectionCard>
            <div className="ops-positive">
              <CheckCircleOutlined />
              <div>
                <Typography.Text strong>Критических событий нет</Typography.Text>
                <Typography.Text type="secondary">Просроченные заявки, ошибки подключений и критические уведомления не обнаружены.</Typography.Text>
              </div>
            </div>
          </SectionCard>
        )}
      </DashboardSection>

      <div className="ops-metrics-grid">
        {data?.metrics.map((metric) => (
          <MetricCard
            key={metric.key}
            icon={metricIcon[metric.key] ?? <FileSearchOutlined />}
            label={metric.label}
            value={metric.value}
            description={metricDescription[metric.key] ?? metric.description}
            tone={metricTone[metric.key] ?? 'info'}
            tooltip={`Расчёт за период: ${formatDate(data.period.date_from)} — ${formatDate(data.period.date_to)}`}
            onClick={() => navigate(metricTarget(metric.key))}
          />
        ))}
      </div>

      <div className="ops-main-grid">
        <DashboardSection
          title="Заявки"
          description="Операционная выборка по текущему периоду."
          className="ops-span-8"
          action={<Button onClick={() => navigate('/applications/contractor-requests')}>Открыть все заявки</Button>}
        >
          <SectionCard>
            <Tabs activeKey={activeRequestGroup} onChange={setActiveRequestGroup} items={requestTabs} />
          </SectionCard>
        </DashboardSection>

        <DashboardSection title="Распределение статусов" description="Сводка по жизненному циклу заявок." className="ops-span-4">
          <SectionCard>
            <ChartCard items={data?.request_status_distribution ?? []} labelForStatus={(status) => requestStatusLabel[status] ?? status} />
          </SectionCard>
        </DashboardSection>
      </div>

      <div className="ops-main-grid">
        <DashboardSection title="Подрядчики" description="Операционная статистика, не формальный SLA." className="ops-span-8">
          <SectionCard>
            {data?.contractor_summary.length ? (
              <CompactDataTable<DashboardContractorSummaryItem> rowKey="contractor_id" columns={contractorColumns} dataSource={data.contractor_summary} />
            ) : (
              <CompactEmptyState title="Активных подрядчиков нет" description="Статистика появится после назначений." />
            )}
          </SectionCard>
        </DashboardSection>

        <DashboardSection title="Ближайшие сроки" description="Сроки выполнения, требующие контроля." className="ops-span-4">
          <SectionCard>
            {data?.upcoming_deadlines.length ? (
              <CompactDataTable<DashboardDeadlineItem> rowKey="request_id" columns={deadlineColumns} dataSource={data.upcoming_deadlines} />
            ) : (
              <CompactEmptyState title="Срочных сроков нет" description="На ближайшие дни нет критичных дедлайнов." />
            )}
          </SectionCard>
        </DashboardSection>
      </div>

      <div className="ops-main-grid">
        <DashboardSection title="Последние события" description="Безопасная лента изменений по доступному контуру." className="ops-span-4">
          <SectionCard>
            <ActivityTimeline items={data?.recent_activity ?? []} renderTime={(value) => formatDate(value, true)} />
          </SectionCard>
        </DashboardSection>

        <DashboardSection title="Уведомления" description={`Непрочитанные: ${data?.notifications.unread_count ?? 0}`} className="ops-span-4">
          <SectionCard>
            {data?.notifications.items.length ? (
              <div className="ops-notifications">
                {data.notifications.items.map((item) => (
                  <article className={`ops-notification ops-tone-${normalizeTone(item.severity)}`} key={item.id}>
                    <BellOutlined />
                    <div>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <small>{item.message}</small>
                      <small>{formatDate(item.created_at, true)}</small>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <CompactEmptyState title="Новых уведомлений нет" description="Критические сообщения появятся в этом блоке." />
            )}
          </SectionCard>
        </DashboardSection>

        <DashboardSection title="Быстрые действия" description="Команды доступны с учётом ваших прав." className="ops-span-4">
          <SectionCard>
            {quickActions.length ? (
              <div className="ops-action-grid">
                {quickActions.map((action) => (
                  <button type="button" className="ops-action-card" key={action.key} onClick={() => navigate(action.target)}>
                    <span>{action.icon}</span>
                    <span>
                      <strong>{action.label}</strong>
                      <small>{action.description}</small>
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <CompactEmptyState title="Нет доступных действий" description="Для вашей роли доступны только просмотровые разделы." />
            )}
          </SectionCard>
        </DashboardSection>
      </div>

      <DashboardSection title="Состояние платформы" description="Безопасная сводка сервисов без раскрытия конфигурационных секретов.">
        <SectionCard>
          <Space direction="vertical" size={16} className="ops-full-width">
            <CompactDataTable<DashboardServiceStatusItem> rowKey="key" columns={serviceColumns} dataSource={data?.system_status ?? []} />
            <Typography.Text type="secondary">Внешние проверки не запускаются при каждой загрузке страницы; используются безопасные статусы конфигурации и последней проверки.</Typography.Text>
          </Space>
        </SectionCard>
      </DashboardSection>
    </div>
  );
}
