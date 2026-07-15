import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';

import { getCurrentUser, getDevUsers } from '../features/admin/services/adminService';
import type { AdminUser, Uuid } from '../features/admin/types';

const STORAGE_KEY = 'security-platform.devUserId';
const DEV_USER_SELECTOR_ENABLED = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_USER_SELECTOR === 'true';

type AuthContextValue = {
  currentUser: AdminUser | null;
  devUsers: AdminUser[];
  loading: boolean;
  status: 'authenticated' | 'unauthorized' | 'forbidden' | 'loading';
  setDevUserId: (userId: Uuid) => void;
  hasPermission: (code: string) => boolean;
  hasAnyPermission: (codes: string[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [currentUser, setCurrentUser] = useState<AdminUser | null>(null);
  const [devUsers, setDevUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<AuthContextValue['status']>('loading');
  const [selectedUserId, setSelectedUserId] = useState<Uuid | null>(() => (DEV_USER_SELECTOR_ENABLED ? localStorage.getItem(STORAGE_KEY) : null) ?? import.meta.env.VITE_DEV_USER_ID ?? null);

  const load = () => {
    setLoading(true);
    Promise.allSettled([DEV_USER_SELECTOR_ENABLED ? getDevUsers() : Promise.resolve([]), selectedUserId ? getCurrentUser() : Promise.reject(new Error('No user'))])
      .then(([devResult, currentResult]) => {
        if (devResult.status === 'fulfilled') {
          setDevUsers(devResult.value);
          if (DEV_USER_SELECTOR_ENABLED && !selectedUserId && devResult.value[0]) {
            localStorage.setItem(STORAGE_KEY, devResult.value[0].id);
            setSelectedUserId(devResult.value[0].id);
          }
        }
        if (currentResult.status === 'fulfilled') {
          setCurrentUser(currentResult.value);
          setStatus('authenticated');
        } else {
          setCurrentUser(null);
          setStatus('unauthorized');
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [selectedUserId]);

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser,
      devUsers,
      loading,
      status,
      setDevUserId: (userId) => {
        localStorage.setItem(STORAGE_KEY, userId);
        setSelectedUserId(userId);
      },
      hasPermission: (code) => Boolean(currentUser?.permissions.includes(code)),
      hasAnyPermission: (codes) => codes.some((code) => currentUser?.permissions.includes(code)),
    }),
    [currentUser, devUsers, loading, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
