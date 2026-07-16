import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { PageLoader } from './components/design-system';
import { ErrorBoundary, RouteErrorBoundary } from './components/errors/ErrorBoundary';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { AppLayout } from './layouts/AppLayout';
import { ChangePasswordPage } from './pages/ChangePasswordPage';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ContractorRoute, LoginRoute, PasswordChangeRoute, PermissionRoute, ProtectedRoute } from './routes/ProtectedRoute';

const AdminAuditPage = lazy(() => import('./features/admin/AdminAuditPage').then((module) => ({ default: module.AdminAuditPage })));
const AdminConnectionsPage = lazy(() => import('./features/admin/AdminConnectionsPage').then((module) => ({ default: module.AdminConnectionsPage })));
const AdminContractorsPage = lazy(() => import('./features/admin/AdminContractorsPage').then((module) => ({ default: module.AdminContractorsPage })));
const AdminDashboardPage = lazy(() => import('./features/admin/AdminDashboardPage').then((module) => ({ default: module.AdminDashboardPage })));
const AdminLayout = lazy(() => import('./features/admin/AdminLayout').then((module) => ({ default: module.AdminLayout })));
const AdminNotificationsPage = lazy(() => import('./features/admin/AdminNotificationsPage').then((module) => ({ default: module.AdminNotificationsPage })));
const AdminReferencePage = lazy(() => import('./features/admin/AdminReferencePage').then((module) => ({ default: module.AdminReferencePage })));
const AdminRolesPage = lazy(() => import('./features/admin/AdminRolesPage').then((module) => ({ default: module.AdminRolesPage })));
const AdminSystemStatusPage = lazy(() => import('./features/admin/AdminSystemStatusPage').then((module) => ({ default: module.AdminSystemStatusPage })));
const AdminUsersPage = lazy(() => import('./features/admin/AdminUsersPage').then((module) => ({ default: module.AdminUsersPage })));
const ApplicationsPage = lazy(() => import('./pages/ApplicationsPage').then((module) => ({ default: module.ApplicationsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })));
const ContractorRequestCreatePage = lazy(() => import('./features/contractor-requests/ContractorRequestCreatePage').then((module) => ({ default: module.ContractorRequestCreatePage })));
const ContractorRequestDetailPage = lazy(() => import('./features/contractor-requests/ContractorRequestDetailPage').then((module) => ({ default: module.ContractorRequestDetailPage })));
const ContractorRequestsListPage = lazy(() => import('./features/contractor-requests/ContractorRequestsListPage').then((module) => ({ default: module.ContractorRequestsListPage })));
const ContractorDashboardPage = lazy(() => import('./features/contractor-portal/ContractorDashboardPage').then((module) => ({ default: module.ContractorDashboardPage })));
const ContractorLayout = lazy(() => import('./features/contractor-portal/ContractorLayout').then((module) => ({ default: module.ContractorLayout })));
const ContractorNotificationsPage = lazy(() => import('./features/contractor-portal/ContractorNotificationsPage').then((module) => ({ default: module.ContractorNotificationsPage })));
const ContractorProfilePage = lazy(() => import('./features/contractor-portal/ContractorProfilePage').then((module) => ({ default: module.ContractorProfilePage })));
const ContractorPortalRequestDetailPage = lazy(() => import('./features/contractor-portal/ContractorRequestDetailPage').then((module) => ({ default: module.ContractorRequestDetailPage })));
const ContractorRequestsPage = lazy(() => import('./features/contractor-portal/ContractorRequestsPage').then((module) => ({ default: module.ContractorRequestsPage })));
const ContractorTasksPage = lazy(() => import('./features/contractor-portal/ContractorTasksPage').then((module) => ({ default: module.ContractorTasksPage })));
const WorkflowCenterPage = lazy(() => import('./features/workflow-center/WorkflowCenterPage').then((module) => ({ default: module.WorkflowCenterPage })));
const WorkflowDefinitionDetailPage = lazy(() => import('./features/workflow-center/WorkflowCenterPage').then((module) => ({ default: module.WorkflowDefinitionDetailPage })));
const WorkflowInstanceDetailPage = lazy(() => import('./features/workflow-center/WorkflowCenterPage').then((module) => ({ default: module.WorkflowInstanceDetailPage })));

const adminAnyPermission = [
  'admin.dashboard.view',
  'admin.contractors.view',
  'admin.users.view',
  'admin.roles.view',
  'admin.audit.view',
  'admin.system_status.view',
  'admin.connections.view',
  'admin.notifications.view',
];

const referenceRoutes = [
  { path: '/admin/cities', resource: 'cities', title: 'Города', description: 'Справочник городов предприятия.' },
  { path: '/admin/facilities', resource: 'facilities', title: 'Объекты', description: 'Объекты предприятия с привязкой к городам.' },
  { path: '/admin/premises', resource: 'premises', title: 'Помещения', description: 'Помещения и контактные данные ответственных.' },
  { path: '/admin/responsibilities', resource: 'responsibilities', title: 'Зоны ответственности', description: 'Назначение подрядчиков на направления работ и объекты.' },
  { path: '/admin/work-types', resource: 'work-types', title: 'Направления работ', description: 'Классификатор работ для Contractor Requests.' },
] as const;

const connectionRoutes = [
  { path: '/admin/connections', tab: 'overview', permission: 'admin.connections.view' },
  { path: '/admin/connections/ldap', tab: 'ldap', permission: 'admin.connections.view' },
  { path: '/admin/connections/adfs', tab: 'adfs', permission: 'admin.connections.view' },
  { path: '/admin/connections/smtp', tab: 'smtp', permission: 'admin.connections.view' },
  { path: '/admin/connections/directory-groups', tab: 'groups', permission: 'admin.directory_groups.view' },
  { path: '/admin/connections/auth-mappings', tab: 'mappings', permission: 'admin.auth_mappings.view' },
  { path: '/admin/connections/logs', tab: 'logs', permission: 'admin.connection_logs.view' },
] as const;

const workflowRoutes = [
  { path: '/admin/workflow-center', permission: 'workflows.instances.view', element: <WorkflowCenterPage page="dashboard" /> },
  { path: '/admin/workflow-center/definitions', permission: 'workflows.view', element: <WorkflowCenterPage page="definitions" /> },
  { path: '/admin/workflow-center/definitions/:definitionId', permission: 'workflows.view', element: <WorkflowDefinitionDetailPage /> },
  { path: '/admin/workflow-center/versions', permission: 'workflows.view', element: <WorkflowCenterPage page="versions" /> },
  { path: '/admin/workflow-center/validation', permission: 'workflows.view', element: <WorkflowCenterPage page="validation" /> },
  { path: '/admin/workflow-center/instances', permission: 'workflows.instances.view', element: <WorkflowCenterPage page="instances" /> },
  { path: '/admin/workflow-center/instances/:instanceId', permission: 'workflows.instances.view', element: <WorkflowInstanceDetailPage /> },
  { path: '/admin/workflow-center/sla', permission: 'workflows.sla.view', element: <WorkflowCenterPage page="sla" /> },
  { path: '/admin/workflow-center/outbox', permission: 'workflows.instances.view', element: <WorkflowCenterPage page="outbox" /> },
  { path: '/admin/workflow-center/audit', permission: 'workflows.view', element: <WorkflowCenterPage page="audit" /> },
  { path: '/admin/workflow-center/health', permission: 'workflows.instances.view', element: <WorkflowCenterPage page="health" /> },
];

function Shell({ children }: { children: ReactNode }) {
  const auth = useAuth();
  return (
    <ProtectedRoute>
      {auth.currentUser?.user_type === 'CONTRACTOR' ? <Navigate to="/contractor" replace /> : <AppLayout>{children}</AppLayout>}
    </ProtectedRoute>
  );
}

function AdminShell({ children }: { children: ReactNode }) {
  return <AdminLayout>{children}</AdminLayout>;
}

function ContractorShell({ children }: { children: ReactNode }) {
  return (
    <ContractorRoute>
      <ContractorLayout>{children}</ContractorLayout>
    </ContractorRoute>
  );
}

function ModuleBoundary({ scope, children }: { scope: string; children: ReactNode }) {
  return (
    <RouteErrorBoundary scope={scope}>
      <Suspense fallback={<PageLoader label="Загрузка раздела" />}>
        {children}
      </Suspense>
    </RouteErrorBoundary>
  );
}

function MainModuleRoute({ scope, children }: { scope: string; children: ReactNode }) {
  return <Shell><ModuleBoundary scope={scope}>{children}</ModuleBoundary></Shell>;
}

function AdminModuleRoute({ scope, permission, anyPermission, children }: { scope: string; permission?: string; anyPermission?: string[]; children: ReactNode }) {
  return (
    <Shell>
      <PermissionRoute permission={permission} anyPermission={anyPermission}>
        <ModuleBoundary scope={scope}>
          <AdminShell>{children}</AdminShell>
        </ModuleBoundary>
      </PermissionRoute>
    </Shell>
  );
}

function ContractorModuleRoute({ scope, children }: { scope: string; children: ReactNode }) {
  return (
    <ModuleBoundary scope={scope}>
      <ContractorShell>{children}</ContractorShell>
    </ModuleBoundary>
  );
}

function AppRoutes() {
  const auth = useAuth();
  return (
    <ErrorBoundary scope="global" onLogout={() => void auth.logout()}>
      <Routes>
        <Route path="/login" element={<LoginRoute><LoginPage /></LoginRoute>} />
        <Route path="/profile/change-password" element={<PasswordChangeRoute><ChangePasswordPage /></PasswordChangeRoute>} />
        <Route path="/" element={<MainModuleRoute scope="Dashboard"><DashboardPage /></MainModuleRoute>} />
        <Route path="/applications" element={<MainModuleRoute scope="Applications"><ApplicationsPage /></MainModuleRoute>} />
        <Route path="/applications/contractor-requests" element={<Shell><PermissionRoute permission="requests.view"><ModuleBoundary scope="Contractor Requests"><ContractorRequestsListPage /></ModuleBoundary></PermissionRoute></Shell>} />
        <Route path="/applications/contractor-requests/new" element={<Shell><PermissionRoute permission="requests.create"><ModuleBoundary scope="Contractor Request Create"><ContractorRequestCreatePage /></ModuleBoundary></PermissionRoute></Shell>} />
        <Route path="/applications/contractor-requests/:requestId" element={<Shell><PermissionRoute permission="requests.view"><ModuleBoundary scope="Contractor Request Detail"><ContractorRequestDetailPage /></ModuleBoundary></PermissionRoute></Shell>} />
        <Route path="/contractor" element={<ContractorModuleRoute scope="Contractor Portal"><ContractorDashboardPage /></ContractorModuleRoute>} />
        <Route path="/contractor/requests" element={<ContractorModuleRoute scope="Contractor Portal Requests"><ContractorRequestsPage /></ContractorModuleRoute>} />
        <Route path="/contractor/requests/:requestId" element={<ContractorModuleRoute scope="Contractor Portal Request Detail"><ContractorPortalRequestDetailPage /></ContractorModuleRoute>} />
        <Route path="/contractor/tasks" element={<ContractorModuleRoute scope="Contractor Portal Tasks"><ContractorTasksPage /></ContractorModuleRoute>} />
        <Route path="/contractor/notifications" element={<ContractorModuleRoute scope="Contractor Portal Notifications"><ContractorNotificationsPage /></ContractorModuleRoute>} />
        <Route path="/contractor/profile" element={<ContractorModuleRoute scope="Contractor Portal Profile"><ContractorProfilePage /></ContractorModuleRoute>} />
        <Route path="/admin" element={<AdminModuleRoute scope="Administration" anyPermission={adminAnyPermission}><AdminDashboardPage /></AdminModuleRoute>} />
        <Route path="/admin/contractors" element={<AdminModuleRoute scope="Administration Contractors" permission="admin.contractors.view"><AdminContractorsPage /></AdminModuleRoute>} />
        <Route path="/admin/users" element={<AdminModuleRoute scope="Administration Users" permission="admin.users.view"><AdminUsersPage /></AdminModuleRoute>} />
        {referenceRoutes.map((route) => (
          <Route key={route.path} path={route.path} element={<AdminModuleRoute scope="Administration Reference" permission="reference_data.manage"><AdminReferencePage resource={route.resource} title={route.title} description={route.description} /></AdminModuleRoute>} />
        ))}
        <Route path="/admin/roles" element={<AdminModuleRoute scope="Administration Roles" permission="admin.roles.view"><AdminRolesPage /></AdminModuleRoute>} />
        <Route path="/admin/audit" element={<AdminModuleRoute scope="Administration Audit" permission="admin.audit.view"><AdminAuditPage /></AdminModuleRoute>} />
        <Route path="/admin/system-status" element={<AdminModuleRoute scope="Administration System Status" permission="admin.system_status.view"><AdminSystemStatusPage /></AdminModuleRoute>} />
        <Route path="/admin/notifications" element={<AdminModuleRoute scope="Administration Notifications" permission="admin.notifications.view"><AdminNotificationsPage /></AdminModuleRoute>} />
        {connectionRoutes.map((route) => (
          <Route key={route.path} path={route.path} element={<AdminModuleRoute scope="Administration Connections" permission={route.permission}><AdminConnectionsPage tab={route.tab} /></AdminModuleRoute>} />
        ))}
        {workflowRoutes.map((route) => (
          <Route key={route.path} path={route.path} element={<AdminModuleRoute scope="Workflow Center" permission={route.permission}>{route.element}</AdminModuleRoute>} />
        ))}
        <Route path="/settings" element={<MainModuleRoute scope="Settings"><SettingsPage /></MainModuleRoute>} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </ErrorBoundary>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
