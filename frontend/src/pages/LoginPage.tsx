import { LockOutlined, LoginOutlined, SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Form, Input, Select, Tooltip, Typography } from 'antd';
import { isAxiosError } from 'axios';
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { PlatformLogo } from '../components/branding';
import { Button } from '../components/design-system';
import { useAuth } from '../context/AuthContext';
import { getAuthProviders } from '../features/admin/services/adminService';
import type { AuthProviderStatus } from '../features/admin/types';

type LoginValues = {
  username: string;
  password: string;
  provider: 'LOCAL' | 'LDAP';
};

type LocationState = {
  from?: {
    pathname?: string;
  };
};

function loginErrorMessage(error: unknown) {
  if (!isAxiosError(error) || !error.response) {
    return 'Сервис авторизации недоступен. Проверьте подключение к backend.';
  }
  if (error.response.status >= 500) {
    return 'Сервис авторизации временно недоступен. Попробуйте позже.';
  }
  if (error.response.status === 400) {
    return 'Выбранный провайдер входа пока не настроен.';
  }
  if (error.response.status === 401) {
    return 'Неверный логин или пароль.';
  }
  if (error.response.status === 403) {
    return 'Учётная запись заблокирована или недоступна. Обратитесь к администратору.';
  }
  return 'Не удалось выполнить вход. Попробуйте ещё раз.';
}

export function LoginPage() {
  const [form] = Form.useForm<LoginValues>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerWarning, setProviderWarning] = useState<string | null>(null);
  const [providers, setProviders] = useState<AuthProviderStatus[]>([]);
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuth();

  useEffect(() => {
    let active = true;
    getAuthProviders()
      .then((items) => {
        if (!active) {
          return;
        }
        setProviders(items);
        setProviderWarning(null);
      })
      .catch((caught: unknown) => {
        if (!active) {
          return;
        }
        if (!isAxiosError(caught) || !caught.response || caught.response.status >= 500) {
          setProviderWarning('Сервис авторизации недоступен. Локальный вход остаётся доступен.');
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const providerByName = useMemo(
    () => new Map(providers.map((item) => [item.provider, item])),
    [providers],
  );
  const adfsEnabled = providerByName.get('ADFS')?.enabled ?? false;
  const ldapEnabled = providerByName.get('LDAP')?.enabled ?? false;

  const submit = async () => {
    const values = await form.validateFields();
    setLoading(true);
    setError(null);
    try {
      const response = await auth.login(values);
      const destination = (location.state as LocationState | null)?.from?.pathname ?? '/';
      const authenticatedDestination = response.user.user_type === 'CONTRACTOR' && destination === '/' ? '/contractor' : destination;
      navigate(response.must_change_password ? '/profile/change-password' : authenticatedDestination, { replace: true });
    } catch (caught) {
      setError(loginErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <PlatformLogo variant="full" className="auth-logo" />
        <div className="auth-heading">
          <Typography.Title id="login-title" level={1} className="sr-only">Security Platform</Typography.Title>
          <Typography.Text>Единая платформа управления сервисами безопасности</Typography.Text>
        </div>

        <div className="auth-provider-block">
          <Typography.Text strong>Вход для внутренних сотрудников</Typography.Text>
          <Button icon={<SafetyCertificateOutlined />} disabled={!adfsEnabled} block>
            Войти через ADFS
          </Button>
          <Typography.Text type="secondary" className="auth-provider-note">
            {adfsEnabled ? 'Корпоративный вход доступен.' : 'Корпоративный вход пока не настроен.'}
          </Typography.Text>
        </div>

        <div className="auth-divider"><span>или</span></div>

        <div className="auth-local-title">
          <Typography.Text strong>Вход для локальных пользователей и подрядчиков</Typography.Text>
        </div>

        {providerWarning ? <Alert className="auth-error" type="warning" showIcon message={providerWarning} /> : null}
        {error ? <Alert className="auth-error" type="error" showIcon message={error} /> : null}

        <Form form={form} layout="vertical" initialValues={{ provider: 'LOCAL' }} onFinish={submit} requiredMark={false}>
          <Form.Item name="provider" label="Тип учётной записи">
            <Select
              options={[
                { value: 'LOCAL', label: 'Локальная' },
                {
                  value: 'LDAP',
                  disabled: !ldapEnabled,
                  label: (
                    <Tooltip title={ldapEnabled ? 'LDAP доступен' : 'LDAP не настроен'} placement="right">
                      <span>Корпоративный каталог</span>
                    </Tooltip>
                  ),
                },
              ]}
            />
          </Form.Item>
          <Form.Item name="username" label="Логин" rules={[{ required: true, message: 'Введите логин' }]}>
            <Input prefix={<UserOutlined />} autoComplete="username" size="large" />
          </Form.Item>
          <Form.Item name="password" label="Пароль" rules={[{ required: true, message: 'Введите пароль' }]}>
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" size="large" />
          </Form.Item>
          <div className="auth-help-row">
            <Link to="/login" onClick={(event) => event.preventDefault()}>Забыли пароль?</Link>
          </div>
          <Button type="primary" htmlType="submit" loading={loading} icon={<LoginOutlined />} block size="large">
            Войти
          </Button>
        </Form>
      </section>
    </main>
  );
}
