import { ErrorState, PageHeader } from '../components/design-system';

export function ForbiddenPage() {
  return (
    <div className="sp-page">
      <PageHeader title="403" description="Недостаточно прав для выбранного раздела или действия." />
      <ErrorState title="Доступ запрещён" description="Обратитесь к администратору Security Platform для изменения роли." />
    </div>
  );
}
