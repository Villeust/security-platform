import { Empty } from 'antd';

type EmptyStateProps = {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  primaryAction?: React.ReactNode;
  secondaryAction?: React.ReactNode;
};

export function EmptyState({ icon, title, description, action, primaryAction, secondaryAction }: EmptyStateProps) {
  return (
    <Empty
      className="sp-empty-state"
      image={icon ?? Empty.PRESENTED_IMAGE_SIMPLE}
      description={
        <span>
          <strong>{title}</strong>
          {description ? <small>{description}</small> : null}
        </span>
      }
    >
      {action ?? primaryAction}
      {secondaryAction}
    </Empty>
  );
}
