import { Empty } from 'antd';

type EmptyStateProps = {
  title: string;
  description?: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<span>{description ?? title}</span>} />;
}
