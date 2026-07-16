import {
  ApiOutlined,
  AuditOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CodeOutlined,
  DashboardOutlined,
  DeploymentUnitOutlined,
  EditOutlined,
  ExportOutlined,
  EyeOutlined,
  FileSearchOutlined,
  ForkOutlined,
  GatewayOutlined,
  HistoryOutlined,
  NodeIndexOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SlidersOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Alert, Button as AntButton, Descriptions, Drawer, Empty, Form, Input, Progress, Select, Space, Statistic, Switch, Tabs, Tag, Timeline, Tooltip, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Button, Card, ErrorState, Loader, PageHeader, Section, StatusBadge, Table } from '../../components/design-system';
import {
  createWorkflowVersion,
  createWorkflowDefinition,
  deactivateWorkflowDefinition,
  getOutboxMonitor,
  getPlatformHealth,
  getProcessAudit,
  getSlaCenter,
  getWorkflowDashboard,
  getWorkflowDefinition,
  getWorkflowDefinitions,
  getWorkflowInstance,
  getWorkflowInstances,
  getWorkflowStatistics,
  getWorkflowVersionDiff,
  getWorkflowVersions,
  publishWorkflowDefinition,
  searchWorkflowCenter,
  updateWorkflowDefinition,
  validateWorkflowDefinition,
} from './service';
import type {
  OutboxMonitor,
  PlatformHealth,
  ProcessAuditItem,
  SlaCenter,
  Uuid,
  WorkflowDashboard,
  WorkflowDefinition,
  WorkflowDefinitionDetail,
  WorkflowInstance,
  WorkflowInstanceDetail,
  WorkflowMetric,
  WorkflowOutboxEvent,
  WorkflowSearchResult,
  WorkflowSlaPolicy,
  WorkflowStatistics,
  WorkflowValidation,
  WorkflowVersion,
  WorkflowVersionDiff,
} from './types';

type PageKind = 'dashboard' | 'definitions' | 'versions' | 'validation' | 'instances' | 'sla' | 'outbox' | 'audit' | 'health';
type DefinitionEditorMode = { mode: 'create' } | { mode: 'edit'; item: WorkflowDefinition };
const CONTRACTOR_REQUEST_WORKFLOW_CODE = 'CONTRACTOR_REQUEST';

const toneMap: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  healthy: 'success',
  ok: 'success',
  Healthy: 'success',
  warning: 'warning',
  attention: 'warning',
  error: 'error',
  critical: 'error',
};

function fmt(value?: string | null) {
  return value ? new Date(value).toLocaleString('ru-RU') : '—';
}

function boolTag(value: boolean, yes = 'Да', no = 'Нет') {
  return <Tag color={value ? 'green' : 'default'}>{value ? yes : no}</Tag>;
}

function humanStatus(value?: string | null) {
  const map: Record<string, string> = {
    Healthy: 'Исправно',
    healthy: 'Исправно',
    ok: 'Исправно',
    warning: 'Предупреждение',
    error: 'Ошибка',
    unknown: 'Неизвестно',
    configured: 'Настроено',
    missing: 'Не настроено',
    skipped: 'Пропущено',
  };
  return value ? map[value] ?? value : '—';
}

function toneForMetric(metric: WorkflowMetric) {
  if (metric.tone === 'error') return 'workflow-metric-error';
  if (metric.tone === 'attention') return 'workflow-metric-warning';
  return 'workflow-metric-healthy';
}

function metricValue(metric?: WorkflowMetric) {
  if (!metric) return 'Нет данных';
  if (metric.value === null || metric.value === undefined || metric.value === '') return 'Нет данных';
  return metric.value;
}

function metricNumber(metric?: WorkflowMetric) {
  if (!metric) return 0;
  if (typeof metric.value === 'number') return metric.value;
  const parsed = Number(String(metric.value).replace('%', ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function healthState(value: number) {
  if (value < 70) return { label: 'Критично', tone: 'error' as const, cardTone: 'critical' };
  if (value < 90) return { label: 'Требует внимания', tone: 'warning' as const, cardTone: 'warning' };
  return { label: 'Стабильно', tone: 'success' as const, cardTone: 'success' };
}

function WorkflowMetricCard({ metric, icon, tone, description, tooltip, badge }: { metric?: WorkflowMetric; icon: ReactNode; tone: 'info' | 'success' | 'warning' | 'critical' | 'neutral'; description: string; tooltip: string; badge?: ReactNode }) {
  const navigate = useNavigate();
  const disabled = !metric?.target;
  const card = (
    <button type="button" className={`workflow-kpi-card workflow-kpi-${tone}`} onClick={() => metric?.target && navigate(metric.target)} disabled={disabled}>
      <span className="workflow-kpi-icon">{icon}</span>
      <span className="workflow-kpi-content">
        <span className="workflow-kpi-value">{metricValue(metric)}</span>
        <span className="workflow-kpi-label">{metric?.label ?? 'Нет данных'}</span>
        <span className="workflow-kpi-description">{description}</span>
        {badge ? <span className="workflow-kpi-badge">{badge}</span> : null}
      </span>
    </button>
  );
  return <Tooltip title={tooltip}>{card}</Tooltip>;
}

function CompactMetric({ metric, description }: { metric?: WorkflowMetric; description: string }) {
  return (
    <Tooltip title={description}>
      <div className={`workflow-compact-metric ${toneForMetric(metric ?? { key: '', label: '', value: '', tone: 'healthy' })}`}>
        <Typography.Text type="secondary">{metric?.label ?? 'Нет данных'}</Typography.Text>
        <strong>{metricValue(metric)}</strong>
      </div>
    </Tooltip>
  );
}

function isProtectedContractorWorkflow(item: WorkflowDefinition) {
  return item.code === CONTRACTOR_REQUEST_WORKFLOW_CODE && item.version === 1;
}

function MetricGrid({ metrics }: { metrics: WorkflowMetric[] }) {
  const navigate = useNavigate();
  return (
    <div className="workflow-metric-grid">
      {metrics.map((metric) => (
        <button type="button" className={`workflow-metric-card ${toneForMetric(metric)}`} key={metric.key} onClick={() => metric.target && navigate(metric.target)}>
          <span className="workflow-metric-label">{metric.label}</span>
          <strong>{metric.value}</strong>
        </button>
      ))}
    </div>
  );
}

function WorkflowSearchBox() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<WorkflowSearchResult[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setItems([]);
      return;
    }
    const timer = window.setTimeout(() => {
      searchWorkflowCenter(query).then(setItems).catch(() => setItems([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <div className="workflow-search">
      <Input prefix={<SearchOutlined />} placeholder="Поиск по процессам, состояниям, переходам, правам и экземплярам" value={query} onChange={(event) => { setQuery(event.target.value); setOpen(true); }} />
      {open && items.length > 0 ? (
        <div className="workflow-search-results">
          {items.map((item) => (
            <button key={`${item.type}-${item.target}-${item.label}`} type="button" onClick={() => { setOpen(false); navigate(item.target); }}>
              <Tag>{item.type}</Tag>
              <span>{item.label}</span>
              <Typography.Text type="secondary">{item.description}</Typography.Text>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PageScaffold({ title, description, children, actions }: { title: string; description: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="sp-page workflow-center-page">
      <PageHeader title={title} description={description} actions={<><WorkflowSearchBox />{actions}</>} />
      {children}
    </div>
  );
}

export function WorkflowCenterPage({ page }: { page: PageKind }) {
  if (page === 'dashboard') return <WorkflowDashboardPage />;
  if (page === 'definitions') return <WorkflowDefinitionsPage />;
  if (page === 'versions') return <WorkflowVersionsPage />;
  if (page === 'validation') return <WorkflowValidationPage />;
  if (page === 'instances') return <WorkflowInstancesPage />;
  if (page === 'sla') return <WorkflowSlaPage />;
  if (page === 'outbox') return <WorkflowOutboxPage />;
  if (page === 'audit') return <WorkflowAuditPage />;
  return <PlatformHealthPage />;
}

export function WorkflowDashboardPage() {
  const [data, setData] = useState<WorkflowDashboard | null>(null);
  const [stats, setStats] = useState<WorkflowStatistics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([getWorkflowDashboard(), getWorkflowStatistics()])
      .then(([dashboard, statistics]) => {
        setData(dashboard);
        setStats(statistics);
      })
      .catch(() => setError('Не удалось загрузить центр процессов.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  if (error) return <ErrorState title="Центр процессов недоступен" description={error} />;
  if (!data || !stats) return <Loader label="Загрузка центра процессов" />;
  const metrics = new Map(data.metrics.map((metric) => [metric.key, metric]));
  const healthMetric = metrics.get('health');
  const health = healthState(metricNumber(healthMetric));
  const primaryMetrics = [
    { key: 'definitions', icon: <DeploymentUnitOutlined />, tone: 'info' as const, description: 'Все версии и шаблоны процессов', tooltip: 'Количество workflow definitions во всех версиях.' },
    { key: 'published', icon: <CheckCircleOutlined />, tone: 'success' as const, description: 'Готовы к использованию', tooltip: 'Опубликованные версии процессов.' },
    { key: 'active_instances', icon: <NodeIndexOutlined />, tone: 'info' as const, description: 'В работе сейчас', tooltip: 'Экземпляры без даты завершения или отмены.' },
    { key: 'sla_violations', icon: <ClockCircleOutlined />, tone: metricNumber(metrics.get('sla_violations')) ? 'critical' as const : 'success' as const, description: 'Таймеры с нарушенным сроком', tooltip: 'Количество SLA timer с зафиксированным нарушением.' },
    { key: 'pending_outbox', icon: <ApiOutlined />, tone: metricNumber(metrics.get('pending_outbox')) ? 'warning' as const : 'success' as const, description: 'Ожидают отправки', tooltip: 'События исходящей очереди в статусе ожидания.' },
    { key: 'health', icon: <SafetyCertificateOutlined />, tone: health.cardTone as 'success' | 'warning' | 'critical', description: 'Сводка Platform Doctor', tooltip: 'Индекс рассчитывается Platform Doctor по базе данных, миграциям, Workflow, RBAC, seed и конфигурации.', badge: <StatusBadge label={health.label} tone={health.tone} /> },
  ];
  const secondaryMetrics = [
    { key: 'drafts', description: 'Неопубликованные версии процессов.' },
    { key: 'completed_today', description: 'Экземпляры, завершенные за текущий день.' },
    { key: 'failed_outbox', description: 'События исходящей очереди с ошибкой.' },
    { key: 'avg_transition', description: 'Средняя длительность переходов, если доступны данные.' },
    { key: 'avg_workflow', description: 'Средняя длительность завершенных процессов.' },
  ];

  return (
    <PageScaffold
      title="Центр процессов"
      description="Управление и контроль процессов Security Platform"
      actions={<Button icon={<ReloadOutlined />} loading={loading} onClick={load}>Обновить</Button>}
    >
      <Section title="Ключевые показатели">
        <div className="workflow-primary-metrics">
          {primaryMetrics.map((item) => (
            <WorkflowMetricCard
              key={item.key}
              metric={metrics.get(item.key)}
              icon={item.icon}
              tone={item.tone}
              description={item.description}
              tooltip={item.tooltip}
              badge={item.badge}
            />
          ))}
        </div>
        <div className="workflow-secondary-metrics">
          {secondaryMetrics.map((item) => <CompactMetric key={item.key} metric={metrics.get(item.key)} description={item.description} />)}
        </div>
      </Section>
      <div className="workflow-two-column">
        <Card title="Статистика выполнения">
          <div className="workflow-stat-grid">
            <Statistic title="Средняя длительность" value={stats.average_workflow_duration} />
            <Statistic title="Медиана" value={stats.median_duration} />
            <Statistic title="Завершение" value={stats.completion_percent} suffix="%" />
            <Statistic title="SLA" value={stats.sla_percent} suffix="%" />
          </div>
        </Card>
        <Card title="Последняя активность">
          {data.recent_activity.length > 0 ? (
            <Timeline
              items={data.recent_activity.map((item) => ({
                color: 'blue',
                dot: <AuditOutlined />,
                children: (
                  <div className="workflow-timeline-item">
                    <strong>{item.action}</strong>
                    <span>{item.workflow_code ?? 'Процесс'} v{item.workflow_version ?? '—'}</span>
                    <Typography.Text type="secondary">{fmt(item.created_at)}</Typography.Text>
                  </div>
                ),
              }))}
            />
          ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Событий пока нет" />}
        </Card>
      </div>
    </PageScaffold>
  );
}

export function WorkflowDefinitionsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [published, setPublished] = useState<string | undefined>();
  const [drawerItem, setDrawerItem] = useState<WorkflowDefinitionDetail | null>(null);
  const [editor, setEditor] = useState<DefinitionEditorMode | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    getWorkflowDefinitions({ search: search || undefined, published: published === undefined ? undefined : published === 'true' })
      .then((response) => setItems(response.items))
      .catch(() => setError('Не удалось загрузить определения процессов.'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const mutate = async (action: 'version' | 'publish' | 'deactivate', id: Uuid) => {
    try {
      if (action === 'version') await createWorkflowVersion(id);
      if (action === 'publish') await publishWorkflowDefinition(id);
      if (action === 'deactivate') await deactivateWorkflowDefinition(id);
      message.success('Операция выполнена');
      load();
    } catch {
      message.error('Операция не выполнена');
    }
  };

  const columns: ColumnsType<WorkflowDefinition> = [
    { title: 'Код', dataIndex: 'code', sorter: (a, b) => a.code.localeCompare(b.code) },
    { title: 'Название', dataIndex: 'name' },
    { title: 'Тип сущности', dataIndex: 'entity_type' },
    { title: 'Версия', dataIndex: 'version', sorter: (a, b) => a.version - b.version },
    { title: 'Публикация', render: (_, item) => boolTag(item.is_published, 'Опубликовано', 'Черновик') },
    { title: 'Активность', render: (_, item) => boolTag(item.is_active, 'Активно', 'Отключено') },
    { title: 'Состояния', dataIndex: 'states_count' },
    { title: 'Переходы', dataIndex: 'transitions_count' },
    { title: 'Экземпляры', dataIndex: 'instances_count' },
    { title: 'Обновлено', render: (_, item) => fmt(item.updated_at) },
    {
      title: 'Действия',
      fixed: 'right',
      render: (_, item) => {
        const protectedWorkflow = isProtectedContractorWorkflow(item);
        return (
        <Space>
          <Tooltip title="Открыть"><AntButton icon={<EyeOutlined />} onClick={() => navigate(`/admin/workflow-center/definitions/${item.id}`)} /></Tooltip>
          <Tooltip title="Просмотр"><AntButton icon={<FileSearchOutlined />} onClick={() => getWorkflowDefinition(item.id).then(setDrawerItem)} /></Tooltip>
          {!protectedWorkflow ? (
            <>
              <Tooltip title="Редактировать"><AntButton icon={<EditOutlined />} disabled={item.is_published} onClick={() => setEditor({ mode: 'edit', item })} /></Tooltip>
              <Tooltip title="Новая версия"><AntButton icon={<BranchesOutlined />} onClick={() => mutate('version', item.id)} /></Tooltip>
              <Tooltip title="Опубликовать"><AntButton icon={<PlayCircleOutlined />} disabled={item.is_published} onClick={() => mutate('publish', item.id)} /></Tooltip>
              <Tooltip title="Деактивировать"><AntButton icon={<SlidersOutlined />} disabled={!item.is_active} onClick={() => mutate('deactivate', item.id)} /></Tooltip>
            </>
          ) : null}
        </Space>
        );
      },
    },
  ];

  if (error) return <ErrorState title="Определения недоступны" description={error} />;

  return (
    <PageScaffold title="Определения процессов" description="Управление универсальными определениями процессов." actions={<Space><Button icon={<PlusOutlined />} onClick={() => setEditor({ mode: 'create' })}>Создать</Button><Button icon={<SearchOutlined />} onClick={load}>Найти</Button></Space>}>
      <Card className="workflow-filter-card">
        <Space wrap>
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Код, название, тип сущности" />
          <Select allowClear placeholder="Публикация" value={published} onChange={setPublished} options={[{ value: 'true', label: 'Опубликовано' }, { value: 'false', label: 'Черновик' }]} style={{ width: 180 }} />
        </Space>
      </Card>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={items} pagination={{ pageSize: 20 }} />
      <DefinitionDrawer item={drawerItem} onClose={() => setDrawerItem(null)} />
      <DefinitionEditorDrawer editor={editor} onClose={() => setEditor(null)} onSaved={() => { setEditor(null); load(); }} />
    </PageScaffold>
  );
}

function DefinitionEditorDrawer({ editor, onClose, onSaved }: { editor: DefinitionEditorMode | null; onClose: () => void; onSaved: () => void }) {
  const [form] = Form.useForm();
  const isEdit = editor?.mode === 'edit';

  useEffect(() => {
    if (!editor) return;
    if (editor.mode === 'create') {
      form.resetFields();
      form.setFieldsValue({ is_active: true });
    } else {
      form.setFieldsValue({
        name: editor.item.name,
        description: editor.item.description,
        is_active: editor.item.is_active,
      });
    }
  }, [editor, form]);

  const save = async () => {
    const values = await form.validateFields();
    try {
      if (editor?.mode === 'create') {
        await createWorkflowDefinition({
          code: values.code,
          name: values.name,
          description: values.description || null,
          entity_type: values.entity_type,
        });
      } else if (editor?.mode === 'edit') {
        await updateWorkflowDefinition(editor.item.id, {
          name: values.name,
          description: values.description || null,
          is_active: values.is_active,
        });
      }
      message.success('Определение сохранено');
      onSaved();
    } catch {
      message.error('Не удалось сохранить определение');
    }
  };

  return (
    <Drawer
      title={isEdit ? 'Редактирование определения' : 'Новое определение'}
      open={!!editor}
      onClose={onClose}
      width="min(640px, 92vw)"
      extra={<Space><AntButton onClick={onClose}>Отмена</AntButton><AntButton type="primary" onClick={save}>Сохранить</AntButton></Space>}
    >
      <Form layout="vertical" form={form}>
        {!isEdit ? (
          <>
            <Form.Item label="Код" name="code" rules={[{ required: true, message: 'Укажите код' }]}>
              <Input placeholder="SECURITY_PROCESS" />
            </Form.Item>
            <Form.Item label="Тип сущности" name="entity_type" rules={[{ required: true, message: 'Укажите тип сущности' }]}>
              <Input placeholder="MODULE_ENTITY" />
            </Form.Item>
          </>
        ) : null}
        <Form.Item label="Название" name="name" rules={[{ required: true, message: 'Укажите название' }]}>
          <Input />
        </Form.Item>
        <Form.Item label="Описание" name="description">
          <Input.TextArea rows={4} />
        </Form.Item>
        <Form.Item label="Активно" name="is_active" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Drawer>
  );
}

function DefinitionDrawer({ item, onClose }: { item: WorkflowDefinitionDetail | null; onClose: () => void }) {
  return (
    <Drawer title={item ? `${item.code} v${item.version}` : ''} open={!!item} onClose={onClose} width="min(920px, 92vw)">
      {item ? <DefinitionDetailContent item={item} /> : null}
    </Drawer>
  );
}

export function WorkflowDefinitionDetailPage() {
  const { definitionId } = useParams();
  const [item, setItem] = useState<WorkflowDefinitionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!definitionId) return;
    getWorkflowDefinition(definitionId).then(setItem).catch(() => setError('Определение процесса не найдено.'));
  }, [definitionId]);

  if (error) return <ErrorState title="Процесс недоступен" description={error} />;
  if (!item) return <Loader label="Загрузка процесса" />;

  return (
    <PageScaffold
      title={`${item.code} v${item.version}`}
      description="Карточка процесса, диаграмма, состояния, переходы, SLA и проверка."
      actions={<a href={`/api/v1/admin/workflow-center/definitions/${item.id}/export?format=json`} target="_blank" rel="noreferrer"><Button icon={<ExportOutlined />}>Экспорт JSON</Button></a>}
    >
      <DefinitionDetailContent item={item} />
    </PageScaffold>
  );
}

function DefinitionDetailContent({ item }: { item: WorkflowDefinitionDetail }) {
  const defaultTab = new URLSearchParams(window.location.search).get('tab') ?? 'overview';
  return (
    <Tabs
      defaultActiveKey={defaultTab}
      items={[
        { key: 'overview', label: 'Обзор', children: <DefinitionOverview item={item} /> },
        { key: 'diagram', label: 'Диаграмма', children: <WorkflowDiagram item={item} /> },
        { key: 'states', label: 'Состояния', children: <StatesTable item={item} /> },
        { key: 'transitions', label: 'Переходы', children: <TransitionsTable item={item} /> },
        { key: 'sla', label: 'SLA', children: <SlaPoliciesTable items={item.sla_policies} /> },
        { key: 'versions', label: 'Версии', children: <InlineVersions code={item.code} /> },
        { key: 'validation', label: 'Проверка', children: <ValidationPanel validation={item.validation} /> },
      ]}
    />
  );
}

function DefinitionOverview({ item }: { item: WorkflowDefinitionDetail }) {
  return (
    <div className="workflow-two-column">
      <Card title="Метаданные">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="Код">{item.code}</Descriptions.Item>
          <Descriptions.Item label="Название">{item.name}</Descriptions.Item>
          <Descriptions.Item label="Тип сущности">{item.entity_type}</Descriptions.Item>
          <Descriptions.Item label="Версия">{item.version}</Descriptions.Item>
          <Descriptions.Item label="Опубликовано">{boolTag(item.is_published)}</Descriptions.Item>
          <Descriptions.Item label="Активно">{boolTag(item.is_active)}</Descriptions.Item>
          <Descriptions.Item label="Дата публикации">{fmt(item.published_at)}</Descriptions.Item>
          <Descriptions.Item label="Создал">{item.created_by ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="Опубликовал">{item.published_by ?? '—'}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="Использование">
        <MetricGrid metrics={[
          { key: 'states', label: 'Состояния', value: item.states_count, tone: 'healthy' },
          { key: 'transitions', label: 'Переходы', value: item.transitions_count, tone: 'healthy' },
          { key: 'instances', label: 'Экземпляры', value: item.instances_count, tone: item.instances_count ? 'healthy' : 'attention' },
          { key: 'validation', label: 'Текущая проверка', value: item.validation.status, tone: item.validation.status === 'error' ? 'error' : item.validation.status === 'warning' ? 'attention' : 'healthy' },
        ]} />
      </Card>
    </div>
  );
}

function WorkflowDiagram({ item }: { item: WorkflowDefinitionDetail }) {
  const width = Math.max(760, item.states.length * 180);
  const y = 120;
  const positions = new Map(item.states.map((state, index) => [state.id, { x: 100 + index * 170, y }]));
  return (
    <Card title="Диаграмма процесса" extra={<Space><Button>По размеру</Button><Button>Масштаб</Button></Space>}>
      <div className="workflow-diagram-wrap">
        <svg width={width} height={260} role="img" aria-label="Диаграмма процесса">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="#4b5563" />
            </marker>
          </defs>
          {item.transitions.map((transition) => {
            const from = positions.get(transition.from_state_id);
            const to = positions.get(transition.to_state_id);
            if (!from || !to) return null;
            const curve = from.x === to.x ? 44 : 0;
            return (
              <g key={transition.id}>
                <path d={`M ${from.x + 58} ${from.y} C ${from.x + 92} ${from.y - curve}, ${to.x - 92} ${to.y - curve}, ${to.x - 58} ${to.y}`} stroke={transition.is_active ? '#4b5563' : '#9ca3af'} strokeWidth="2" fill="none" markerEnd="url(#arrow)" />
                <title>{`${transition.name}\n${transition.from_state_code} → ${transition.to_state_code}\nПраво: ${transition.permission_code ?? '—'}`}</title>
              </g>
            );
          })}
          {item.states.map((state) => {
            const pos = positions.get(state.id)!;
            const cls = state.is_initial ? 'workflow-node-initial' : state.is_terminal ? 'workflow-node-terminal' : !state.is_active ? 'workflow-node-inactive' : 'workflow-node-active';
            return (
              <g key={state.id} transform={`translate(${pos.x - 58} ${pos.y - 34})`} className={cls}>
                <rect width="116" height="68" rx="8" />
                <text x="58" y="28" textAnchor="middle">{state.code}</text>
                <text x="58" y="48" textAnchor="middle" className="workflow-node-sub">{state.outgoing_count} исх. / {state.incoming_count} вх.</text>
                <title>{`${state.name}\n${state.description ?? ''}\nИсходящие: ${state.outgoing_count}\nВходящие: ${state.incoming_count}`}</title>
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
}

function StatesTable({ item }: { item: WorkflowDefinitionDetail }) {
  return (
    <Table
      rowKey="id"
      columns={[
        { title: 'Код', dataIndex: 'code' },
        { title: 'Название', dataIndex: 'name' },
        { title: 'Описание', dataIndex: 'description' },
        { title: 'Цвет', dataIndex: 'color_token', render: (value) => <span className="workflow-swatch" style={{ background: value ?? '#d1d5db' }} /> },
        { title: 'Иконка', dataIndex: 'icon' },
        { title: 'Начальное', render: (_, row) => boolTag(row.is_initial) },
        { title: 'Терминальное', render: (_, row) => boolTag(row.is_terminal) },
        { title: 'Порядок', dataIndex: 'sort_order' },
        { title: 'Активно', render: (_, row) => boolTag(row.is_active) },
      ]}
      dataSource={item.states}
      pagination={{ pageSize: 20 }}
    />
  );
}

function TransitionsTable({ item }: { item: WorkflowDefinitionDetail }) {
  return (
    <Table
      rowKey="id"
      columns={[
        { title: 'Код', dataIndex: 'code' },
        { title: 'Название', dataIndex: 'name' },
        { title: 'Из', dataIndex: 'from_state_code' },
        { title: 'В', dataIndex: 'to_state_code' },
        { title: 'Право', dataIndex: 'permission_code' },
        { title: 'Комментарий', render: (_, row) => boolTag(row.requires_comment) },
        { title: 'Причина', render: (_, row) => boolTag(row.requires_reason) },
        { title: 'Вложение', render: (_, row) => boolTag(row.requires_attachment) },
        { title: 'Подтверждение', render: (_, row) => boolTag(row.confirmation_required) },
        { title: 'Активно', render: (_, row) => boolTag(row.is_active) },
      ]}
      dataSource={item.transitions}
      pagination={{ pageSize: 20 }}
    />
  );
}

function SlaPoliciesTable({ items }: { items: WorkflowSlaPolicy[] }) {
  return (
    <Table
      rowKey="id"
      columns={[
        { title: 'Код', dataIndex: 'code' },
        { title: 'Название', dataIndex: 'name' },
        { title: 'Состояние', dataIndex: 'state_code' },
        { title: 'Переход', dataIndex: 'transition_code' },
        { title: 'Длительность', dataIndex: 'duration_label' },
        { title: 'Предупреждение', dataIndex: 'warning_label' },
        { title: 'Важность', dataIndex: 'severity' },
        { title: 'Статус', render: (_, row) => boolTag(row.is_active, 'Активно', 'Отключено') },
      ]}
      dataSource={items}
      pagination={{ pageSize: 20 }}
    />
  );
}

function ValidationPanel({ validation }: { validation: WorkflowValidation }) {
  const rows = [...validation.errors, ...validation.warnings, ...validation.info];
  return (
    <div className="workflow-validation-list">
      {rows.map((issue) => (
        <Alert key={`${issue.severity}-${issue.code}-${issue.message}`} type={issue.severity === 'error' ? 'error' : issue.severity === 'warning' ? 'warning' : 'info'} showIcon message={issue.code} description={issue.message} />
      ))}
    </div>
  );
}

function InlineVersions({ code }: { code: string }) {
  const [items, setItems] = useState<WorkflowVersion[]>([]);
  useEffect(() => { getWorkflowVersions({ code }).then((response) => setItems(response.items)); }, [code]);
  return <VersionsTable items={items} />;
}

export function WorkflowValidationPage() {
  const [definitions, setDefinitions] = useState<WorkflowDefinition[]>([]);
  const [selected, setSelected] = useState<Uuid | undefined>();
  const [validation, setValidation] = useState<WorkflowValidation | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getWorkflowDefinitions().then((response) => { setDefinitions(response.items); setSelected(response.items[0]?.id); }).catch(() => setError('Не удалось загрузить список процессов.')); }, []);
  useEffect(() => { if (selected) validateWorkflowDefinition(selected).then(setValidation).catch(() => setError('Не удалось выполнить проверку процесса.')); }, [selected]);
  if (error) return <ErrorState title="Проверка недоступна" description={error} />;
  return (
    <PageScaffold title="Проверка процессов" description="Проверка процесса без публикации.">
      <Card><Select value={selected} onChange={setSelected} style={{ minWidth: 360 }} options={definitions.map((item) => ({ value: item.id, label: `${item.code} v${item.version}` }))} /></Card>
      {definitions.length === 0 ? <Empty description="Определений процессов пока нет" /> : validation ? <ValidationPanel validation={validation} /> : <Loader label="Загрузка проверки" />}
    </PageScaffold>
  );
}

export function WorkflowVersionsPage() {
  const [items, setItems] = useState<WorkflowVersion[]>([]);
  const [diff, setDiff] = useState<WorkflowVersionDiff | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getWorkflowVersions().then((response) => setItems(response.items)).catch(() => setError('Не удалось загрузить версии процессов.')).finally(() => setLoading(false)); }, []);
  const compare = () => {
    if (items.length >= 2) getWorkflowVersionDiff(items[1].id, items[0].id).then(setDiff).catch(() => setError('Не удалось сравнить версии.'));
  };
  if (error) return <ErrorState title="Версии недоступны" description={error} />;
  if (loading) return <Loader label="Загрузка версий" />;
  return (
    <PageScaffold title="Версии процессов" description="Версии процессов, публикация, деактивация и сравнение." actions={<Button icon={<ForkOutlined />} onClick={compare}>Сравнить последние</Button>}>
      <VersionsTable items={items} />
      {items.length === 0 ? <Empty description="Версий пока нет" /> : null}
      {diff ? <VersionDiff diff={diff} /> : null}
    </PageScaffold>
  );
}

function VersionsTable({ items }: { items: WorkflowVersion[] }) {
  return (
    <Table
      rowKey="id"
      columns={[
        { title: 'Версия', dataIndex: 'version' },
        { title: 'Статус', dataIndex: 'status', render: (value) => <Tag color={value === 'published' ? 'green' : 'blue'}>{value}</Tag> },
        { title: 'Создал', dataIndex: 'created_by' },
        { title: 'Создано', render: (_, row) => fmt(row.created_at) },
        { title: 'Опубликовано', render: (_, row) => fmt(row.published_at) },
        { title: 'Комментарий', dataIndex: 'comment' },
        { title: 'Экземпляры', dataIndex: 'instances_count' },
        { title: 'Действия', render: (_, row) => <Link to={`/admin/workflow-center/definitions/${row.id}`}>Открыть</Link> },
      ]}
      dataSource={items}
      pagination={{ pageSize: 20 }}
    />
  );
}

function VersionDiff({ diff }: { diff: WorkflowVersionDiff }) {
  const groups = [
    ['Добавленные состояния', diff.added_states, 'green'],
    ['Удаленные состояния', diff.removed_states, 'red'],
    ['Добавленные переходы', diff.added_transitions, 'green'],
    ['Удаленные переходы', diff.removed_transitions, 'red'],
    ['Изменения прав', diff.permission_changes, 'orange'],
    ['Изменения SLA', diff.sla_changes, 'orange'],
    ['Изменения метаданных', diff.metadata_changes, 'blue'],
  ] as const;
  return (
    <Section title={`Сравнение v${diff.source_version} → v${diff.target_version}`}>
      <div className="workflow-diff-grid">
        {groups.map(([title, values, color]) => (
          <Card key={title} title={title}>{values.length ? values.map((value) => <Tag key={value} color={color}>{value}</Tag>) : <Typography.Text type="secondary">Изменений нет</Typography.Text>}</Card>
        ))}
      </div>
    </Section>
  );
}

export function WorkflowInstancesPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<WorkflowInstance[]>([]);
  const [search, setSearch] = useState('');
  const [active, setActive] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setLoading(true);
    setError(null);
    getWorkflowInstances({ search: search || undefined, active: active === undefined ? undefined : active === 'true' })
      .then((response) => setItems(response.items))
      .catch(() => setError('Не удалось загрузить экземпляры процессов.'))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);
  if (error) return <ErrorState title="Экземпляры недоступны" description={error} />;
  return (
    <PageScaffold title="Экземпляры процессов" description="Операционный просмотр экземпляров процессов." actions={<Button icon={<SearchOutlined />} onClick={load}>Найти</Button>}>
      <Card><Space wrap><Input placeholder="Процесс, состояние, номер заявки" value={search} onChange={(event) => setSearch(event.target.value)} /><Select allowClear placeholder="Статус" value={active} onChange={setActive} options={[{ value: 'true', label: 'Активные' }, { value: 'false', label: 'Завершенные' }]} style={{ width: 180 }} /></Space></Card>
      <Table
        rowKey="id"
        loading={loading}
        columns={[
          { title: 'Процесс', dataIndex: 'workflow_code' },
          { title: 'Версия', dataIndex: 'workflow_version' },
          { title: 'Сущность', dataIndex: 'entity_type' },
          { title: 'Бизнес-идентификатор', dataIndex: 'business_identifier' },
          { title: 'Текущее состояние', dataIndex: 'current_state_code' },
          { title: 'Запущено', render: (_, row) => fmt(row.started_at) },
          { title: 'Обновлено', render: (_, row) => fmt(row.updated_at) },
          { title: 'Завершено', render: (_, row) => fmt(row.completed_at) },
          { title: 'Версия блокировки', dataIndex: 'lock_version' },
          { title: 'Действия', render: (_, row) => <AntButton icon={<EyeOutlined />} onClick={() => navigate(`/admin/workflow-center/instances/${row.id}`)} /> },
        ]}
        dataSource={items}
        pagination={{ pageSize: 20 }}
      />
    </PageScaffold>
  );
}

export function WorkflowInstanceDetailPage() {
  const { instanceId } = useParams();
  const [item, setItem] = useState<WorkflowInstanceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (instanceId) getWorkflowInstance(instanceId).then(setItem).catch(() => setError('Экземпляр процесса не найден.')); }, [instanceId]);
  if (error) return <ErrorState title="Экземпляр недоступен" description={error} />;
  if (!item) return <Loader label="Загрузка экземпляра" />;
  return (
    <PageScaffold title={item.business_identifier} description="Детальная карточка экземпляра процесса.">
      <div className="workflow-two-column">
        <Card title="Текущее состояние"><StatusBadge label={item.current_state_code} tone="success" /><Descriptions column={1} size="small"><Descriptions.Item label="Процесс">{item.workflow_code} v{item.workflow_version}</Descriptions.Item><Descriptions.Item label="Запущено">{fmt(item.started_at)}</Descriptions.Item><Descriptions.Item label="Версия блокировки">{item.lock_version}</Descriptions.Item></Descriptions></Card>
        <Card title="Связанная сущность"><Descriptions column={1} size="small"><Descriptions.Item label="Сущность">{item.entity_type}</Descriptions.Item><Descriptions.Item label="Бизнес ID">{item.business_identifier}</Descriptions.Item></Descriptions></Card>
      </div>
      <Section title="История переходов">
        <Timeline items={item.executions.map((execution) => ({ color: 'blue', dot: <ThunderboltOutlined />, children: <div className="workflow-timeline-item"><strong>{execution.transition_code}</strong><span>{execution.from_state} → {execution.to_state}</span><Typography.Text type="secondary">{fmt(execution.created_at)} · {execution.actor_type} · {execution.correlation_id ?? 'без корреляции'}</Typography.Text></div> }))} />
        {item.executions.length === 0 ? <Empty description="Переходов пока нет" /> : null}
      </Section>
      <Section title="Таймеры SLA"><SlaTimersTable items={item.sla_timers} /></Section>
      <Section title="События исходящей очереди"><OutboxTable items={item.outbox_events} /></Section>
      {item.technical_details ? <Card title="Технические детали"><pre>{JSON.stringify(item.technical_details, null, 2)}</pre></Card> : null}
    </PageScaffold>
  );
}

function SlaTimersTable({ items }: { items: Array<{ id: Uuid; policy_code: string | null; policy_name: string | null; due_at: string; status: string }> }) {
  return <Table rowKey="id" columns={[{ title: 'Политика', dataIndex: 'policy_code' }, { title: 'Название', dataIndex: 'policy_name' }, { title: 'Срок', render: (_, row) => fmt(row.due_at) }, { title: 'Статус', dataIndex: 'status' }]} dataSource={items} pagination={{ pageSize: 10 }} />;
}

export function WorkflowSlaPage() {
  const [data, setData] = useState<SlaCenter | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getSlaCenter().then(setData).catch(() => setError('Не удалось загрузить центр SLA.')); }, []);
  if (error) return <ErrorState title="SLA недоступен" description={error} />;
  if (!data) return <Loader label="Загрузка центра SLA" />;
  return (
    <PageScaffold title="Центр SLA" description="Политики SLA и таймеры процессов.">
      <Alert type="info" showIcon message={data.business_calendar_note} />
      <MetricGrid metrics={data.metrics} />
      <Section title="Политики"><SlaPoliciesTable items={data.policies} /></Section>
      <Section title="Таймеры"><SlaTimersTable items={data.timers} /></Section>
    </PageScaffold>
  );
}

export function WorkflowOutboxPage() {
  const [data, setData] = useState<OutboxMonitor | null>(null);
  const [status, setStatus] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    setError(null);
    getOutboxMonitor({ status }).then(setData).catch(() => setError('Не удалось загрузить монитор событий.'));
  };
  useEffect(() => { load(); }, []);
  if (error) return <ErrorState title="Монитор событий недоступен" description={error} />;
  if (!data) return <Loader label="Загрузка монитора событий" />;
  return (
    <PageScaffold title="Монитор событий" description="Безопасный просмотр событий доменной шины без исходного payload." actions={<Button onClick={load}>Обновить</Button>}>
      <MetricGrid metrics={data.metrics} />
      <Card><Select allowClear placeholder="Статус" value={status} onChange={setStatus} options={['PENDING', 'PROCESSING', 'PROCESSED', 'FAILED'].map((value) => ({ value, label: value }))} style={{ width: 220 }} /></Card>
      <OutboxTable items={data.items} />
    </PageScaffold>
  );
}

function OutboxTable({ items }: { items: WorkflowOutboxEvent[] }) {
  return <Table rowKey="id" columns={[{ title: 'Событие', dataIndex: 'event_type' }, { title: 'Процесс', dataIndex: 'aggregate_type' }, { title: 'Сущность', dataIndex: 'business_identifier' }, { title: 'Создано', render: (_, row) => fmt(row.created_at) }, { title: 'Статус', dataIndex: 'status' }, { title: 'Попытки', dataIndex: 'attempts' }, { title: 'Корреляция', dataIndex: 'correlation_id' }]} dataSource={items} pagination={{ pageSize: 20 }} />;
}

export function WorkflowAuditPage() {
  const [items, setItems] = useState<ProcessAuditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getProcessAudit().then((response) => setItems(response.items)).catch(() => setError('Не удалось загрузить аудит процессов.')).finally(() => setLoading(false)); }, []);
  if (error) return <ErrorState title="Аудит недоступен" description={error} />;
  if (loading) return <Loader label="Загрузка аудита" />;
  return (
    <PageScaffold title="Аудит процессов" description="События жизненного цикла процессов и версий.">
      <Table rowKey="id" columns={[{ title: 'Действие', dataIndex: 'action' }, { title: 'Процесс', dataIndex: 'workflow_code' }, { title: 'Версия', dataIndex: 'workflow_version' }, { title: 'Пользователь', dataIndex: 'actor_id' }, { title: 'Дата', render: (_, row) => fmt(row.created_at) }]} dataSource={items} pagination={{ pageSize: 20 }} />
      {items.length === 0 ? <Empty description="Событий аудита пока нет" /> : null}
    </PageScaffold>
  );
}

export function PlatformHealthPage() {
  const [data, setData] = useState<PlatformHealth | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getPlatformHealth().then(setData).catch(() => setError('Не удалось загрузить состояние платформы.')); }, []);
  if (error) return <ErrorState title="Состояние платформы недоступно" description={error} />;
  if (!data) return <Loader label="Загрузка состояния платформы" />;
  const cards = [
    ['Backend', data.backend_status],
    ['База данных', data.database_status],
    ['Ревизия Alembic', data.alembic_revision ?? '—'],
    ['Движок процессов', data.workflow_engine],
    ['Определения процессов', data.workflow_definitions],
    ['Экземпляры процессов', data.workflow_instances],
    ['RBAC', data.rbac],
    ['Аутентификация', data.authentication],
    ['Хранилище', data.storage],
    ['SMTP', data.smtp],
    ['LDAP', data.ldap],
    ['ADFS', data.adfs],
  ];
  return (
    <PageScaffold title="Состояние платформы" description="Операционный обзор состояния платформы безопасности.">
      <Card title="Индекс состояния платформы"><Progress percent={data.health_score} status={data.errors.length ? 'exception' : data.warnings.length ? 'active' : 'success'} /></Card>
      <div className="workflow-health-grid">
        {cards.map(([name, status]) => <Card key={name} title={name}><StatusBadge label={humanStatus(status)} tone={toneMap[status] ?? 'neutral'} /></Card>)}
      </div>
      <Section title="Предупреждения диагностики">{data.warnings.length ? data.warnings.map((item) => <Alert key={item.name} type="warning" showIcon message={item.name} description={item.message} />) : <Empty description="Предупреждений нет" />}</Section>
      <Section title="Ошибки диагностики">{data.errors.length ? data.errors.map((item) => <Alert key={item.name} type="error" showIcon message={item.name} description={item.message} />) : <Empty description="Ошибок нет" />}</Section>
    </PageScaffold>
  );
}
