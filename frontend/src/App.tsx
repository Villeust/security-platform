import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import type { ReactNode } from 'react';

import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { AdminAuditPage } from './features/admin/AdminAuditPage';
import { AdminConnectionsPage } from './features/admin/AdminConnectionsPage';
import { AdminContractorsPage } from './features/admin/AdminContractorsPage';
import { AdminDashboardPage } from './features/admin/AdminDashboardPage';
import { AdminLayout } from './features/admin/AdminLayout';
import { AdminNotificationsPage } from './features/admin/AdminNotificationsPage';
import { AdminReferencePage } from './features/admin/AdminReferencePage';
import { AdminRolesPage } from './features/admin/AdminRolesPage';
import { AdminSystemStatusPage } from './features/admin/AdminSystemStatusPage';
import { AdminUsersPage } from './features/admin/AdminUsersPage';
import { ContractorRequestCreatePage } from './features/contractor-requests/ContractorRequestCreatePage';
import { ContractorRequestDetailPage } from './features/contractor-requests/ContractorRequestDetailPage';
import { ContractorRequestsListPage } from './features/contractor-requests/ContractorRequestsListPage';
import { ContractorDashboardPage } from './features/contractor-portal/ContractorDashboardPage';
import { ContractorLayout } from './features/contractor-portal/ContractorLayout';
import { ContractorNotificationsPage } from './features/contractor-portal/ContractorNotificationsPage';
import { ContractorProfilePage } from './features/contractor-portal/ContractorProfilePage';
import { ContractorRequestDetailPage as ContractorPortalRequestDetailPage } from './features/contractor-portal/ContractorRequestDetailPage';
import { ContractorRequestsPage } from './features/contractor-portal/ContractorRequestsPage';
import { ContractorTasksPage } from './features/contractor-portal/ContractorTasksPage';
import { AppLayout } from './layouts/AppLayout';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { ChangePasswordPage } from './pages/ChangePasswordPage';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { SettingsPage } from './pages/SettingsPage';
import { ContractorRoute, LoginRoute, PasswordChangeRoute, PermissionRoute, ProtectedRoute } from './routes/ProtectedRoute';

function Shell({ children }: { children: ReactNode }) {
  const auth = useAuth();
  return (
    <ProtectedRoute>
      {auth.currentUser?.user_type === 'CONTRACTOR' ? <Navigate to="/contractor" replace /> : <AppLayout>{children}</AppLayout>}
    </ProtectedRoute>
  );
}

function AdminShell({ children }: { children: ReactNode }) {
  return (
    <AdminLayout>{children}</AdminLayout>
  );
}

function ContractorShell({ children }: { children: ReactNode }) {
  return (
    <ContractorRoute>
      <ContractorLayout>{children}</ContractorLayout>
    </ContractorRoute>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginRoute><LoginPage /></LoginRoute>} />
            <Route path="/profile/change-password" element={<PasswordChangeRoute><ChangePasswordPage /></PasswordChangeRoute>} />
            <Route path="/" element={<Shell><DashboardPage /></Shell>} />
            <Route path="/applications" element={<Shell><ApplicationsPage /></Shell>} />
            <Route path="/applications/contractor-requests" element={<Shell><PermissionRoute permission="requests.view"><ContractorRequestsListPage /></PermissionRoute></Shell>} />
            <Route path="/applications/contractor-requests/new" element={<Shell><PermissionRoute permission="requests.create"><ContractorRequestCreatePage /></PermissionRoute></Shell>} />
            <Route path="/applications/contractor-requests/:requestId" element={<Shell><PermissionRoute permission="requests.view"><ContractorRequestDetailPage /></PermissionRoute></Shell>} />
            <Route path="/contractor" element={<ContractorShell><ContractorDashboardPage /></ContractorShell>} />
            <Route path="/contractor/requests" element={<ContractorShell><ContractorRequestsPage /></ContractorShell>} />
            <Route path="/contractor/requests/:requestId" element={<ContractorShell><ContractorPortalRequestDetailPage /></ContractorShell>} />
            <Route path="/contractor/tasks" element={<ContractorShell><ContractorTasksPage /></ContractorShell>} />
            <Route path="/contractor/notifications" element={<ContractorShell><ContractorNotificationsPage /></ContractorShell>} />
            <Route path="/contractor/profile" element={<ContractorShell><ContractorProfilePage /></ContractorShell>} />
            <Route path="/admin" element={<Shell><PermissionRoute anyPermission={['admin.dashboard.view', 'admin.contractors.view', 'admin.users.view', 'admin.roles.view', 'admin.audit.view', 'admin.system_status.view', 'admin.connections.view', 'admin.notifications.view']}><AdminShell><AdminDashboardPage /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/contractors" element={<Shell><PermissionRoute permission="admin.contractors.view"><AdminShell><AdminContractorsPage /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/users" element={<Shell><PermissionRoute permission="admin.users.view"><AdminShell><AdminUsersPage /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/cities" element={<Shell><PermissionRoute permission="reference_data.manage"><AdminShell><AdminReferencePage resource="cities" title="Города" description="Справочник городов предприятия." /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/facilities" element={<Shell><PermissionRoute permission="reference_data.manage"><AdminShell><AdminReferencePage resource="facilities" title="Объекты" description="Объекты предприятия с привязкой к городам." /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/premises" element={<Shell><PermissionRoute permission="reference_data.manage"><AdminShell><AdminReferencePage resource="premises" title="Помещения" description="Помещения и контактные данные ответственных." /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/responsibilities" element={<Shell><PermissionRoute permission="reference_data.manage"><AdminShell><AdminReferencePage resource="responsibilities" title="Зоны ответственности" description="Назначение подрядчиков на направления работ и объекты." /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/work-types" element={<Shell><PermissionRoute permission="reference_data.manage"><AdminShell><AdminReferencePage resource="work-types" title="Направления работ" description="Классификатор работ для Contractor Requests." /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/roles" element={<Shell><PermissionRoute permission="admin.roles.view"><AdminShell><AdminRolesPage /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/audit" element={<Shell><PermissionRoute permission="admin.audit.view"><AdminShell><AdminAuditPage /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/system-status" element={<Shell><PermissionRoute permission="admin.system_status.view"><AdminShell><AdminSystemStatusPage /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/notifications" element={<Shell><PermissionRoute permission="admin.notifications.view"><AdminShell><AdminNotificationsPage /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/connections" element={<Shell><PermissionRoute permission="admin.connections.view"><AdminShell><AdminConnectionsPage tab="overview" /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/connections/ldap" element={<Shell><PermissionRoute permission="admin.connections.view"><AdminShell><AdminConnectionsPage tab="ldap" /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/connections/adfs" element={<Shell><PermissionRoute permission="admin.connections.view"><AdminShell><AdminConnectionsPage tab="adfs" /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/connections/smtp" element={<Shell><PermissionRoute permission="admin.connections.view"><AdminShell><AdminConnectionsPage tab="smtp" /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/connections/directory-groups" element={<Shell><PermissionRoute permission="admin.directory_groups.view"><AdminShell><AdminConnectionsPage tab="groups" /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/connections/auth-mappings" element={<Shell><PermissionRoute permission="admin.auth_mappings.view"><AdminShell><AdminConnectionsPage tab="mappings" /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/admin/connections/logs" element={<Shell><PermissionRoute permission="admin.connection_logs.view"><AdminShell><AdminConnectionsPage tab="logs" /></AdminShell></PermissionRoute></Shell>} />
            <Route path="/settings" element={<Shell><SettingsPage /></Shell>} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
