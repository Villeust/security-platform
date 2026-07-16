import { Alert, Form, Input, Typography, message } from 'antd';
import { isAxiosError } from 'axios';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { Button, Card } from '../components/design-system';
import { useAuth } from '../context/AuthContext';

type ChangePasswordValues = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

function changePasswordErrorMessage(error: unknown) {
  if (!isAxiosError(error) || !error.response) {
    return 'Сервис авторизации недоступен. Проверьте подключение к backend.';
  }

  const detail = error.response.data?.detail;
  if (error.response.status === 401) {
    return 'Сессия истекла. Войдите снова.';
  }
  if (error.response.status === 403) {
    if (detail === 'CURRENT_PASSWORD_INVALID') {
      return 'Текущий пароль указан неверно.';
    }
    if (detail === 'CSRF_TOKEN_INVALID') {
      return 'Сессия устарела. Обновите страницу и попробуйте снова.';
    }
    return 'Недостаточно прав для изменения пароля.';
  }
  if (error.response.status === 409 && detail === 'PASSWORD_REUSE_NOT_ALLOWED') {
    return 'Новый пароль не должен совпадать с текущим.';
  }
  if (error.response.status === 422) {
    const details = Array.isArray(detail) ? detail.map((item) => item.msg ?? item).join(' ') : detail;
    if (String(details).includes('PASSWORD_CONFIRMATION_MISMATCH')) {
      return 'Новый пароль и подтверждение не совпадают.';
    }
    if (details === 'LOCAL_PASSWORD_NOT_AVAILABLE') {
      return 'Для этой учётной записи локальный пароль недоступен.';
    }
    if (details === 'PASSWORD_TOO_SHORT') {
      return 'Пароль должен содержать минимум 12 символов.';
    }
    if (details === 'PASSWORD_TOO_LONG') {
      return 'Пароль слишком длинный.';
    }
    if (details === 'PASSWORD_REQUIRES_UPPERCASE') {
      return 'Пароль должен содержать заглавную букву.';
    }
    if (details === 'PASSWORD_REQUIRES_LOWERCASE') {
      return 'Пароль должен содержать строчную букву.';
    }
    if (details === 'PASSWORD_REQUIRES_DIGIT') {
      return 'Пароль должен содержать цифру.';
    }
    if (details === 'PASSWORD_REQUIRES_SPECIAL') {
      return 'Пароль должен содержать специальный символ.';
    }
    if (details === 'PASSWORD_EQUALS_USERNAME') {
      return 'Пароль не должен совпадать с логином.';
    }
    return 'Пароль не соответствует требованиям политики безопасности.';
  }
  if (error.response.status >= 500) {
    return 'Сервис авторизации временно недоступен. Попробуйте позже.';
  }
  return 'Не удалось изменить пароль. Проверьте введённые данные.';
}

export function ChangePasswordPage() {
  const [form] = Form.useForm<ChangePasswordValues>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isRequired = auth.status === 'password_change_required' || Boolean(auth.currentUser?.must_change_password || auth.currentUser?.password_expired);
  const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? '/';

  const submit = async () => {
    if (loading) {
      return;
    }
    const values = await form.validateFields();
    setError(null);
    setLoading(true);
    try {
      await auth.changePassword(values.current_password, values.new_password, values.confirm_password);
      message.success('Пароль успешно изменён');
      navigate(destination === '/profile/change-password' ? '/' : destination, { replace: true });
    } catch (caught) {
      setError(changePasswordErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    await auth.logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="auth-page">
      <Card className="auth-card">
        <Typography.Title level={2}>{isRequired ? 'Необходимо изменить временный пароль' : 'Смена пароля'}</Typography.Title>
        <Typography.Paragraph type="secondary">
          {isRequired ? 'Для продолжения работы задайте новый пароль.' : 'Обновите пароль локальной учётной записи.'}
        </Typography.Paragraph>
        <Alert
          className="auth-error"
          type="info"
          showIcon
          message="Требования к паролю"
          description="Минимум 12 символов, заглавная и строчная буквы, цифра и специальный символ. Пароль не должен совпадать с логином или текущим паролем."
        />
        {error ? <Alert className="auth-error" type="error" showIcon message={error} /> : null}
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="current_password" label="Текущий пароль" rules={[{ required: true, message: 'Введите текущий пароль' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item name="new_password" label="Новый пароль" rules={[{ required: true, min: 12, message: 'Минимум 12 символов' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="Повторите пароль"
            dependencies={['new_password']}
            rules={[
              { required: true, message: 'Повторите новый пароль' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  return !value || getFieldValue('new_password') === value ? Promise.resolve() : Promise.reject(new Error('Пароли не совпадают'));
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} disabled={loading} className="auth-submit">
            Сохранить пароль
          </Button>
          <Button type="default" block onClick={logout} disabled={loading}>
            Выйти
          </Button>
        </Form>
      </Card>
    </div>
  );
}
