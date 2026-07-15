import { Alert } from 'antd';

type ErrorStateProps = {
  title: string;
  description?: string;
};

export function ErrorState({ title, description }: ErrorStateProps) {
  return <Alert type="error" showIcon message={title} description={description} />;
}
