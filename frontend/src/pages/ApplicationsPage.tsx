import {
  BarChartOutlined,
  IdcardOutlined,
  SafetyCertificateOutlined,
  UserSwitchOutlined,
  VideoCameraOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { NavigationCard, PlatformPage, PlatformPageHeader, PlatformSection } from '../components/design-system';

const plannedModules = [
  {
    icon: <UserSwitchOutlined />,
    title: 'Управление доступом',
    description: 'Контроль пропусков, зон доступа и согласований.',
  },
  {
    icon: <VideoCameraOutlined />,
    title: 'Видеонаблюдение',
    description: 'Рабочее место мониторинга камер и событий.',
  },
  {
    icon: <IdcardOutlined />,
    title: 'Посетители',
    description: 'Регистрация гостей, пропуска и сопровождение.',
  },
  {
    icon: <WarningOutlined />,
    title: 'Инциденты',
    description: 'Регистрация и контроль расследования инцидентов.',
  },
  {
    icon: <BarChartOutlined />,
    title: 'Отчётность',
    description: 'Операционные отчёты и аналитика безопасности.',
  },
];

export function ApplicationsPage() {
  const navigate = useNavigate();

  return (
    <PlatformPage>
      <PlatformPageHeader title="Модули" description="Рабочие модули Security Platform" />

      <PlatformSection title="Доступные модули" description="Операционные разделы, доступные вашей роли.">
        <div className="sp-module-grid">
          <NavigationCard
            icon={<SafetyCertificateOutlined />}
            title="Заявки подрядчикам"
            description="Назначение подрядчиков, контроль сроков, результатов работ, комментариев и вложений."
            status="Доступно"
            onClick={() => navigate('/applications/contractor-requests')}
          />
        </div>
      </PlatformSection>

      <PlatformSection title="Будущие направления" description="Разделы платформы, которые будут подключаться по мере развития продукта.">
        <div className="sp-module-grid">
          {plannedModules.map((item) => (
            <NavigationCard key={item.title} icon={item.icon} title={item.title} description={item.description} status="Будет доступно позже" disabled />
          ))}
        </div>
      </PlatformSection>
    </PlatformPage>
  );
}
