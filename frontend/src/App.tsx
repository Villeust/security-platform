import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { ThemeProvider } from './context/ThemeContext';
import { AppLayout } from './layouts/AppLayout';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { DashboardPage } from './pages/DashboardPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { SettingsPage } from './pages/SettingsPage';
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
        <AppLayout>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/applications" element={<ApplicationsPage />} />
            <Route path="/applications/contractor-requests" element={<ContractorRequestsListPage />} />
            <Route path="/applications/contractor-requests/new" element={<ContractorRequestCreatePage />} />
            <Route path="/applications/contractor-requests/:requestId" element={<ContractorRequestDetailPage />} />
            <Route path="/admin" element={<AdminLayout><AdminDashboardPage /></AdminLayout>} />
            <Route path="/admin/contractors" element={<AdminLayout><AdminContractorsPage /></AdminLayout>} />
            <Route path="/admin/users" element={<AdminLayout><AdminUsersPage /></AdminLayout>} />
            <Route path="/admin/cities" element={<AdminLayout><AdminReferencePage resource="cities" title="Города" description="Справочник городов предприятия." /></AdminLayout>} />
            <Route path="/admin/facilities" element={<AdminLayout><AdminReferencePage resource="facilities" title="Объекты" description="Объекты предприятия с привязкой к городам." /></AdminLayout>} />
            <Route path="/admin/premises" element={<AdminLayout><AdminReferencePage resource="premises" title="Помещения" description="Помещения и контактные данные ответственных." /></AdminLayout>} />
            <Route path="/admin/responsibilities" element={<AdminLayout><AdminReferencePage resource="responsibilities" title="Зоны ответственности" description="Назначение подрядчиков на направления работ и объекты." /></AdminLayout>} />
            <Route path="/admin/work-types" element={<AdminLayout><AdminReferencePage resource="work-types" title="Направления работ" description="Классификатор работ для Contractor Requests." /></AdminLayout>} />
            <Route path="/admin/roles" element={<AdminLayout><AdminRolesPage /></AdminLayout>} />
            <Route path="/admin/audit" element={<AdminLayout><AdminAuditPage /></AdminLayout>} />
            <Route path="/admin/system-status" element={<AdminLayout><AdminSystemStatusPage /></AdminLayout>} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </ThemeProvider>
  );
}
