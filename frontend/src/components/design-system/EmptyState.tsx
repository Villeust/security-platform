import { Empty } from 'antd';

type EmptyStateProps = {
  title: string;
  description?: string;
  action?: React.ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <Empty
      className="sp-empty-state"
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description={
        <span>
          <strong>{title}</strong>
          {description ? <small>{description}</small> : null}
        </span>
      }
    >
      {action}
    </Empty>
  );
}
