import { EmptyState, PageHeader, SearchBar, Section } from '../components/design-system';

export function ApplicationsPage() {
  return (
    <div className="sp-page">
      <PageHeader title="Applications" description="Application workspace placeholder." />
      <Section title="Applications" actions={<SearchBar placeholder="Search applications" />}>
        <EmptyState title="No applications" description="Application UI will be added after backend review." />
      </Section>
    </div>
  );
}
