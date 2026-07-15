import type { PropsWithChildren } from 'react';

import { Loader } from '../components/design-system';
import { useAuth } from '../context/AuthContext';
import { ForbiddenPage } from '../pages/ForbiddenPage';
import { UnauthorizedPage } from '../pages/UnauthorizedPage';

type PermissionRouteProps = PropsWithChildren<{
  permission?: string;
  anyPermission?: string[];
}>;

export function ProtectedRoute({ children }: PropsWithChildren) {
  const auth = useAuth();
  if (auth.loading) return <Loader label="Проверка доступа" />;
  if (!auth.currentUser) return <UnauthorizedPage />;
  return <>{children}</>;
}

export function PermissionRoute({ permission, anyPermission, children }: PermissionRouteProps) {
  const auth = useAuth();
  if (auth.loading) return <Loader label="Проверка доступа" />;
  if (!auth.currentUser) return <UnauthorizedPage />;
  const allowed = permission ? auth.hasPermission(permission) : anyPermission ? auth.hasAnyPermission(anyPermission) : true;
  if (!allowed) return <ForbiddenPage />;
  return <>{children}</>;
}
