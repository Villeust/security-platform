import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { AppLayout } from './layouts/AppLayout';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { DashboardPage } from './pages/DashboardPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { SettingsPage } from './pages/SettingsPage';
import { PermissionRoute } from './routes/ProtectedRoute';
import { AdminAuditPage } from './features/admin/AdminAuditPage';
import { AdminContractorsPage } from './features/admin/AdminContractorsPage';
import { AdminDashboardPage } from './features/admin/AdminDashboardPage';
import { AdminLayout } from './features/admin/AdminLayout';
import { AdminReferencePage } from './features/admin/AdminReferencePage';
import { AdminRolesPage } from './features/admin/AdminRolesPage';
import { AdminSystemStatusPage } from './features/admin/AdminSystemStatusPage';
import { AdminUsersPage } from './features/admin/AdminUsersPage';
import { ContractorRequestCreatePage } from './features/contractor-requests/ContractorRequestCreatePage';
import { ContractorRequestDetailPage } from './features/contractor-requests/ContractorRequestDetailPage';
import { ContractorRequestsListPage } from './features/contractor-requests/ContractorRequestsListPage';

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <AppLayout>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/applications" element={<ApplicationsPage />} />
              <Route path="/applications/contractor-requests" element={<PermissionRoute permission="requests.view"><ContractorRequestsListPage /></PermissionRoute>} />
              <Route path="/applications/contractor-requests/new" element={<PermissionRoute permission="requests.create"><ContractorRequestCreatePage /></PermissionRoute>} />
              <Route path="/applications/contractor-requests/:requestId" element={<PermissionRoute permission="requests.view"><ContractorRequestDetailPage /></PermissionRoute>} />
              <Route path="/admin" element={<PermissionRoute anyPermission={['admin.dashboard.view', 'admin.contractors.view', 'admin.users.view', 'admin.roles.view', 'admin.audit.view', 'admin.system_status.view']}><AdminLayout><AdminDashboardPage /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/contractors" element={<PermissionRoute permission="admin.contractors.view"><AdminLayout><AdminContractorsPage /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/users" element={<PermissionRoute permission="admin.users.view"><AdminLayout><AdminUsersPage /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/cities" element={<PermissionRoute permission="reference_data.manage"><AdminLayout><AdminReferencePage resource="cities" title="Города" description="Справочник городов предприятия." /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/facilities" element={<PermissionRoute permission="reference_data.manage"><AdminLayout><AdminReferencePage resource="facilities" title="Объекты" description="Объекты предприятия с привязкой к городам." /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/premises" element={<PermissionRoute permission="reference_data.manage"><AdminLayout><AdminReferencePage resource="premises" title="Помещения" description="Помещения и контактные данные ответственных." /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/responsibilities" element={<PermissionRoute permission="reference_data.manage"><AdminLayout><AdminReferencePage resource="responsibilities" title="Зоны ответственности" description="Назначение подрядчиков на направления работ и объекты." /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/work-types" element={<PermissionRoute permission="reference_data.manage"><AdminLayout><AdminReferencePage resource="work-types" title="Направления работ" description="Классификатор работ для Contractor Requests." /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/roles" element={<PermissionRoute permission="admin.roles.view"><AdminLayout><AdminRolesPage /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/audit" element={<PermissionRoute permission="admin.audit.view"><AdminLayout><AdminAuditPage /></AdminLayout></PermissionRoute>} />
              <Route path="/admin/system-status" element={<PermissionRoute permission="admin.system_status.view"><AdminLayout><AdminSystemStatusPage /></AdminLayout></PermissionRoute>} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </AppLayout>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
