import type { PropsWithChildren } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { Loader } from '../components/design-system';
import { useAuth } from '../context/AuthContext';
import { ForbiddenPage } from '../pages/ForbiddenPage';

type PermissionRouteProps = PropsWithChildren<{
  permission?: string;
  anyPermission?: string[];
}>;

export function ProtectedRoute({ children }: PropsWithChildren) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.loading) return <Loader label="Проверка доступа" />;
  if (!auth.currentUser) return <Navigate to="/login" state={{ from: location }} replace />;
  if (auth.currentUser.must_change_password && location.pathname !== '/profile/change-password') {
    return <Navigate to="/profile/change-password" replace />;
  }
  return <>{children}</>;
}

export function PermissionRoute({ permission, anyPermission, children }: PermissionRouteProps) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.loading) return <Loader label="Проверка доступа" />;
  if (!auth.currentUser) return <Navigate to="/login" state={{ from: location }} replace />;
  if (auth.currentUser.must_change_password && location.pathname !== '/profile/change-password') {
    return <Navigate to="/profile/change-password" replace />;
  }
  const allowed = permission ? auth.hasPermission(permission) : anyPermission ? auth.hasAnyPermission(anyPermission) : true;
  if (!allowed) return <ForbiddenPage />;
  return <>{children}</>;
}
