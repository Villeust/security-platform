import { ErrorState, PageHeader } from '../components/design-system';

export function UnauthorizedPage() {
  return (
    <div className="sp-page">
      <PageHeader title="401" description="Не удалось определить пользователя Security Platform." />
      <ErrorState title="Требуется авторизация" description="Для локальной разработки выберите dev-пользователя в заголовке." />
    </div>
  );
}
