import type { PropsWithChildren } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { Alert } from 'antd';

import { Loader } from '../components/design-system';
import { useAuth } from '../context/AuthContext';
import { ForbiddenPage } from '../pages/ForbiddenPage';

type PermissionRouteProps = PropsWithChildren<{
  permission?: string;
  anyPermission?: string[];
}>;

function AuthErrorState() {
  const auth = useAuth();
  return (
    <main className="auth-page">
      <Alert
        className="auth-card"
        type="error"
        showIcon
        message="Сервис авторизации недоступен"
        description={auth.errorMessage ?? 'Проверьте подключение к backend и попробуйте обновить страницу.'}
      />
    </main>
  );
}

export function LoginRoute({ children }: PropsWithChildren) {
  const auth = useAuth();
  const location = useLocation();
  const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/';
  const authenticatedDestination = auth.currentUser?.user_type === 'CONTRACTOR' && destination === '/' ? '/contractor' : destination;

  if (auth.status === 'loading') return <Loader label="Проверка доступа" />;
  if (auth.status === 'error') return <AuthErrorState />;
  if (auth.status === 'password_change_required') return <Navigate to="/profile/change-password" state={{ from: { pathname: destination } }} replace />;
  if (auth.status === 'authenticated') return <Navigate to={authenticatedDestination} replace />;
  return <>{children}</>;
}

export function PasswordChangeRoute({ children }: PropsWithChildren) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === 'loading') return <Loader label="Проверка доступа" />;
  if (auth.status === 'error') return <AuthErrorState />;
  if (auth.status === 'unauthenticated') return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

export function ProtectedRoute({ children }: PropsWithChildren) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === 'loading') return <Loader label="Проверка доступа" />;
  if (auth.status === 'error') return <AuthErrorState />;
  if (auth.status === 'unauthenticated') return <Navigate to="/login" state={{ from: location }} replace />;
  if (auth.status === 'password_change_required') {
    return <Navigate to="/profile/change-password" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

export function ContractorRoute({ children }: PropsWithChildren) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === 'loading') return <Loader label="РџСЂРѕРІРµСЂРєР° РґРѕСЃС‚СѓРїР°" />;
  if (auth.status === 'error') return <AuthErrorState />;
  if (auth.status === 'unauthenticated') return <Navigate to="/login" state={{ from: location }} replace />;
  if (auth.status === 'password_change_required') {
    return <Navigate to="/profile/change-password" state={{ from: location }} replace />;
  }
  if (auth.currentUser?.user_type !== 'CONTRACTOR' || !auth.hasPermission('contractor.portal.view')) {
    return <ForbiddenPage />;
  }
  return <>{children}</>;
}

export function PermissionRoute({ permission, anyPermission, children }: PermissionRouteProps) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === 'loading') return <Loader label="Проверка доступа" />;
  if (auth.status === 'error') return <AuthErrorState />;
  if (auth.status === 'unauthenticated') return <Navigate to="/login" state={{ from: location }} replace />;
  if (auth.status === 'password_change_required') {
    return <Navigate to="/profile/change-password" state={{ from: location }} replace />;
  }

  const allowed = permission ? auth.hasPermission(permission) : anyPermission ? auth.hasAnyPermission(anyPermission) : true;
  if (!allowed) return <ForbiddenPage />;
  return <>{children}</>;
}
