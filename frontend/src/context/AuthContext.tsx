import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';

import {
  changePassword as changePasswordRequest,
  getAuthMe,
  getDevUsers,
  login as loginRequest,
  logout as logoutRequest,
} from '../features/admin/services/adminService';
import type { AdminUser, LoginResponse, Uuid } from '../features/admin/types';

const STORAGE_KEY = 'security-platform.devUserId';
export const DEV_USER_SELECTOR_ENABLED = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_USER_SELECTOR === 'true';

type LoginPayload = {
  username: string;
  password: string;
  provider?: 'LOCAL' | 'LDAP';
};

type AuthContextValue = {
  currentUser: AdminUser | null;
  devUsers: AdminUser[];
  loading: boolean;
  status: 'authenticated' | 'unauthorized' | 'forbidden' | 'loading';
  setDevUserId: (userId: Uuid) => void;
  login: (payload: LoginPayload) => Promise<LoginResponse>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  reload: () => Promise<void>;
  hasPermission: (code: string) => boolean;
  hasAnyPermission: (codes: string[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function initialDevUserId() {
  if (DEV_USER_SELECTOR_ENABLED) {
    return localStorage.getItem(STORAGE_KEY) ?? import.meta.env.VITE_DEV_USER_ID ?? null;
  }
  return import.meta.env.VITE_DEV_USER_ID ?? null;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [currentUser, setCurrentUser] = useState<AdminUser | null>(null);
  const [devUsers, setDevUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<AuthContextValue['status']>('loading');
  const [selectedUserId, setSelectedUserId] = useState<Uuid | null>(initialDevUserId);

  const reload = async () => {
    setLoading(true);
    try {
      const [devResult, currentResult] = await Promise.allSettled([
        DEV_USER_SELECTOR_ENABLED ? getDevUsers() : Promise.resolve([]),
        getAuthMe(),
      ]);
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
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, [selectedUserId]);

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
      login: async (payload) => {
        const response = await loginRequest(payload);
        setCurrentUser(response.user);
        setStatus('authenticated');
        return response;
      },
      logout: async () => {
        await logoutRequest();
        setCurrentUser(null);
        setStatus('unauthorized');
      },
      changePassword: async (currentPassword, newPassword) => {
        await changePasswordRequest(currentPassword, newPassword);
        await reload();
      },
      reload,
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
