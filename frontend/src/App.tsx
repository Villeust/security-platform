import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { ThemeProvider } from './context/ThemeContext';
import { AppLayout } from './layouts/AppLayout';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { DashboardPage } from './pages/DashboardPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { SettingsPage } from './pages/SettingsPage';
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
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </ThemeProvider>
  );
}
