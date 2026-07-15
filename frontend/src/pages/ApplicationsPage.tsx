import { SafetyCertificateOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { Button, Card, PageHeader, SearchBar, Section } from '../components/design-system';

export function ApplicationsPage() {
  const navigate = useNavigate();

  return (
    <div className="sp-page">
      <PageHeader title="Applications" description="Рабочие модули Security Platform." />
      <Section title="Applications" actions={<SearchBar placeholder="Search applications" />}>
        <div className="sp-app-grid">
          <Card
            title={
              <span className="sp-card-title">
                <SafetyCertificateOutlined /> Contractor Requests
              </span>
            }
          >
            <p className="sp-card-text">Заявки подрядчикам на направления СКУД и СВН.</p>
            <Button type="primary" onClick={() => navigate('/applications/contractor-requests')}>
              Открыть
            </Button>
          </Card>
        </div>
      </Section>
    </div>
  );
}
