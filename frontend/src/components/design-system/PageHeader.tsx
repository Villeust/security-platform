import { Space, Typography } from 'antd';
import type { ReactNode } from 'react';

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="sp-page-header">
      <div>
        <Typography.Title level={1} className="sp-page-title">
          {title}
        </Typography.Title>
        {description ? (
          <Typography.Text type="secondary" className="sp-page-description">
            {description}
          </Typography.Text>
        ) : null}
      </div>
      {actions ? <Space>{actions}</Space> : null}
    </div>
  );
}
