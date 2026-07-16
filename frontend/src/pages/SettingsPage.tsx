import { CheckCircleOutlined, ClockCircleOutlined, DesktopOutlined, GlobalOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { Descriptions, Segmented, Tag, Typography } from 'antd';

import { PlatformCard, PlatformPage, PlatformPageHeader, PlatformSection, StatusPill } from '../components/design-system';
import { useAppTheme } from '../context/ThemeContext';

export function SettingsPage() {
  const { appName, mode } = useAppTheme();
  const apiUrl = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

  return (
    <PlatformPage>
      <PlatformPageHeader title="Настройки" description="Параметры интерфейса и рабочей области Security Platform" />

      <PlatformSection title="Интерфейс" description="Визуальные параметры текущей рабочей области.">
        <PlatformCard>
          <div className="sp-settings-card">
            <span className="sp-settings-icon"><DesktopOutlined /></span>
            <div>
              <Typography.Title level={3}>Тема интерфейса</Typography.Title>
              <Typography.Text type="secondary">Сейчас включена светлая корпоративная тема. Переключение тем будет доступно позже.</Typography.Text>
              <Segmented
                className="sp-settings-segmented"
                value={mode}
                options={[
                  { label: 'Светлая', value: 'light' },
                  { label: 'Тёмная', value: 'dark', disabled: true },
                  { label: 'Системная', value: 'system', disabled: true },
                ]}
              />
            </div>
          </div>
        </PlatformCard>
      </PlatformSection>

      <PlatformSection title="Рабочая область" description="Параметры отображения данных.">
        <div className="sp-settings-grid">
          <PlatformCard>
            <Descriptions column={1} className="sp-info-list" items={[
              { key: 'start', label: 'Стартовая страница', children: 'Центр управления' },
              { key: 'density', label: 'Плотность таблиц', children: 'Компактная' },
              { key: 'date', label: 'Формат даты', children: 'Русский региональный формат' },
              { key: 'timezone', label: 'Часовой пояс', children: Intl.DateTimeFormat().resolvedOptions().timeZone },
              { key: 'language', label: 'Язык интерфейса', children: <Tag color="blue">Русский</Tag> },
            ]} />
          </PlatformCard>
          <PlatformCard>
            <div className="sp-settings-card">
              <span className="sp-settings-icon"><GlobalOutlined /></span>
              <div>
                <Typography.Title level={3}>Локализация</Typography.Title>
                <Typography.Text type="secondary">Интерфейс внутренней рабочей области унифицирован на русском языке.</Typography.Text>
                <StatusPill label="Включено" tone="success" />
              </div>
            </div>
          </PlatformCard>
        </div>
      </PlatformSection>

      <PlatformSection title="Уведомления" description="Настройки персональных уведомлений.">
        <PlatformCard>
          <div className="sp-settings-card">
            <span className="sp-settings-icon sp-settings-icon-muted"><ClockCircleOutlined /></span>
            <div>
              <Typography.Title level={3}>Персональные предпочтения</Typography.Title>
              <Typography.Text type="secondary">Тонкая настройка in-app и browser-уведомлений будет доступна позже.</Typography.Text>
              <StatusPill label="Будет доступно позже" tone="neutral" />
            </div>
          </div>
        </PlatformCard>
      </PlatformSection>

      <PlatformSection title="О системе" description="Информация о текущем окружении.">
        <div className="sp-settings-grid">
          <PlatformCard>
            <div className="sp-settings-card">
              <span className="sp-settings-icon"><InfoCircleOutlined /></span>
              <div>
                <Typography.Title level={3}>{appName}</Typography.Title>
                <Typography.Text type="secondary">Внутренняя рабочая область Security Platform</Typography.Text>
                <div className="sp-settings-tags">
                  <StatusPill label={`Окружение: ${import.meta.env.DEV ? 'Разработка' : 'Production'}`} tone="info" />
                  <StatusPill label="Версия 0.1.0" tone="neutral" />
                </div>
              </div>
            </div>
          </PlatformCard>
          <PlatformCard>
            <div className="sp-settings-card">
              <span className="sp-settings-icon"><CheckCircleOutlined /></span>
              <div>
                <Typography.Title level={3}>Backend API</Typography.Title>
                <Typography.Text type="secondary">{apiUrl}</Typography.Text>
                <StatusPill label="Настроено" tone="success" />
              </div>
            </div>
          </PlatformCard>
        </div>
      </PlatformSection>
    </PlatformPage>
  );
}
