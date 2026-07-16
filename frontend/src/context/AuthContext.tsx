import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { isAxiosError } from 'axios';

import {
  changePassword as changePasswordRequest,
  getAuthMe,
  getDevUsers,
  login as loginRequest,
  logout as logoutRequest,
} from '../features/admin/services/adminService';
import type { AdminUser, LoginResponse, Uuid } from '../features/admin/types';
import { setDevUserHeader } from '../services/api';

const DEV_USER_STORAGE_KEY = 'security-platform.devUserId';
export const DEV_USER_SELECTOR_ENABLED = import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_USER_SELECTOR === 'true';

export type AuthStatus = 'loading' | 'unauthenticated' | 'authenticated' | 'password_change_required' | 'error';

type LoginPayload = {
  username: string;
  password: string;
  provider?: 'LOCAL' | 'LDAP';
};

type AuthContextValue = {
  currentUser: AdminUser | null;
  devUsers: AdminUser[];
  loading: boolean;
  status: AuthStatus;
  errorMessage: string | null;
  setDevUserId: (userId: Uuid) => void;
  resetLocalSession: () => Promise<void>;
  login: (payload: LoginPayload) => Promise<LoginResponse>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string, newPasswordConfirmation: string) => Promise<void>;
  reload: () => Promise<void>;
  hasPermission: (code: string) => boolean;
  hasAnyPermission: (codes: string[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function statusForUser(user: AdminUser): AuthStatus {
  return user.must_change_password || user.password_expired ? 'password_change_required' : 'authenticated';
}

function authErrorMessage(error: unknown) {
  if (!isAxiosError(error) || !error.response) {
    return 'Сервис авторизации недоступен. Проверьте подключение к backend.';
  }
  if (error.response.status >= 500) {
    return 'Сервис авторизации временно недоступен. Попробуйте позже.';
  }
  return 'Сессия устарела. Выполните вход повторно.';
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [currentUser, setCurrentUser] = useState<AdminUser | null>(null);
  const [devUsers, setDevUsers] = useState<AdminUser[]>([]);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const clearDevAuthState = () => {
    localStorage.removeItem(DEV_USER_STORAGE_KEY);
    setDevUserHeader(null);
  };

  const reload = async () => {
    setStatus('loading');
    setErrorMessage(null);
    try {
      const [devResult, currentResult] = await Promise.allSettled([
        DEV_USER_SELECTOR_ENABLED ? getDevUsers() : Promise.resolve([]),
        getAuthMe(),
      ]);
      if (devResult.status === 'fulfilled') {
        setDevUsers(devResult.value);
      }
      if (currentResult.status === 'fulfilled') {
        setCurrentUser(currentResult.value);
        setStatus(statusForUser(currentResult.value));
        return;
      }

      const reason = currentResult.reason;
      setCurrentUser(null);
      clearDevAuthState();
      if (isAxiosError(reason) && reason.response?.status === 401) {
        setStatus('unauthenticated');
        return;
      }
      if (isAxiosError(reason) && reason.response?.status === 403) {
        setStatus('unauthenticated');
        setErrorMessage('Сессия устарела. Выполните вход повторно.');
        return;
      }
      setStatus('error');
      setErrorMessage(authErrorMessage(reason));
    } catch (caught) {
      setCurrentUser(null);
      setStatus('error');
      setErrorMessage(authErrorMessage(caught));
    }
  };

  useEffect(() => {
    clearDevAuthState();
    void reload();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      currentUser,
      devUsers,
      loading: status === 'loading',
      status,
      errorMessage,
      setDevUserId: (userId) => {
        if (!DEV_USER_SELECTOR_ENABLED) {
          return;
        }
        localStorage.setItem(DEV_USER_STORAGE_KEY, userId);
        setDevUserHeader(userId);
        void reload();
      },
      resetLocalSession: async () => {
        try {
          await logoutRequest();
        } catch {
          // The goal is local recovery; stale cookies may already be invalid.
        }
        clearDevAuthState();
        setCurrentUser(null);
        setStatus('unauthenticated');
        setErrorMessage(null);
      },
      login: async (payload) => {
        clearDevAuthState();
        const response = await loginRequest(payload);
        setCurrentUser(response.user);
        setStatus(statusForUser(response.user));
        setErrorMessage(null);
        return response;
      },
      logout: async () => {
        try {
          await logoutRequest();
        } finally {
          clearDevAuthState();
          setCurrentUser(null);
          setStatus('unauthenticated');
          setErrorMessage(null);
        }
      },
      changePassword: async (currentPassword, newPassword, newPasswordConfirmation) => {
        await changePasswordRequest(currentPassword, newPassword, newPasswordConfirmation);
        await reload();
      },
      reload,
      hasPermission: (code) => Boolean(currentUser?.permissions.includes(code)),
      hasAnyPermission: (codes) => codes.some((code) => currentUser?.permissions.includes(code)),
    }),
    [currentUser, devUsers, status, errorMessage],
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
