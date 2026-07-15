import { Form, Input, Typography, message } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button, Card } from '../components/design-system';
import { useAuth } from '../context/AuthContext';

type ChangePasswordValues = {
  current_password: string;
  new_password: string;
  confirm_password: string;
};

export function ChangePasswordPage() {
  const [form] = Form.useForm<ChangePasswordValues>();
  const [loading, setLoading] = useState(false);
  const auth = useAuth();
  const navigate = useNavigate();

  const submit = async () => {
    const values = await form.validateFields();
    setLoading(true);
    try {
      await auth.changePassword(values.current_password, values.new_password);
      message.success('Пароль обновлён');
      navigate('/', { replace: true });
    } catch {
      message.error('Не удалось изменить пароль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <Card className="auth-card">
        <Typography.Title level={2}>Смена пароля</Typography.Title>
        <Typography.Paragraph type="secondary">
          Для продолжения работы задайте новый локальный пароль.
        </Typography.Paragraph>
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="current_password" label="Текущий пароль" rules={[{ required: true, message: 'Введите текущий пароль' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item name="new_password" label="Новый пароль" rules={[{ required: true, min: 10, message: 'Минимум 10 символов' }]}>
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
          <Button type="primary" htmlType="submit" loading={loading} className="auth-submit">
            Сохранить пароль
          </Button>
        </Form>
      </Card>
    </div>
  );
}
