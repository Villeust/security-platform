import { Card, PageHeader, Section, StatusBadge } from '../components/design-system';
import { useAppTheme } from '../context/ThemeContext';

export function SettingsPage() {
  const { appName, mode } = useAppTheme();

  return (
    <div className="sp-page">
      <PageHeader title="Settings" description="Shared frontend configuration." />
      <Section title="Theme">
        <div className="sp-settings-grid">
          <Card title="Application">{appName}</Card>
          <Card title="Theme mode">
            <StatusBadge label={mode} tone="processing" />
          </Card>
        </div>
      </Section>
    </div>
  );
}
