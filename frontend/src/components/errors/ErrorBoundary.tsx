import { HomeOutlined, LogoutOutlined, ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import { Button, Result, Space, Typography } from 'antd';
import { Component, type ErrorInfo, type PropsWithChildren, type ReactNode } from 'react';

import { copyCorrelationId, getLastCorrelationId } from '../../lib/correlation';

type ErrorBoundaryProps = PropsWithChildren<{
  scope: string;
  fallback?: ReactNode;
  onLogout?: () => void;
}>;

type ErrorBoundaryState = {
  error: Error | null;
  correlationId: string | null;
};

function reportFrontendError(error: Error, info: ErrorInfo, scope: string, correlationId: string | null) {
  if (import.meta.env.DEV) {
    console.error(`[Security Platform] ${scope} render failure`, { error, info, correlationId });
  }
  // Future integration point: Sentry/OpenTelemetry frontend error exporter.
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, correlationId: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error, correlationId: getLastCorrelationId() };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    reportFrontendError(error, info, this.props.scope, this.state.correlationId);
  }

  retry = () => {
    this.setState({ error: null, correlationId: null });
  };

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    const correlationId = this.state.correlationId;
    const isGlobal = this.props.scope === 'global';

    return (
      <div className="sp-page sp-error-boundary" role="alert">
        <Result
          status="error"
          title="Ошибка приложения"
          subTitle="Что-то пошло не так."
          extra={(
            <Space wrap>
              <Button type="primary" icon={<ReloadOutlined />} onClick={this.retry}>Повторить</Button>
              <Button icon={<HomeOutlined />} onClick={() => { window.location.href = '/'; }}>На главную</Button>
              {this.props.onLogout ? <Button icon={<LogoutOutlined />} onClick={this.props.onLogout}>Выйти</Button> : null}
              {correlationId ? <Button icon={<CopyOutlined />} onClick={() => void copyCorrelationId(correlationId)}>Скопировать ID</Button> : null}
            </Space>
          )}
        >
          {correlationId ? (
            <Typography.Paragraph type="secondary">
              Reference: <Typography.Text code>{correlationId}</Typography.Text>
            </Typography.Paragraph>
          ) : null}
          {import.meta.env.DEV && isGlobal ? <pre className="sp-error-stack">{this.state.error.stack}</pre> : null}
        </Result>
      </div>
    );
  }
}

export function RouteErrorBoundary({ children, scope }: PropsWithChildren<{ scope: string }>) {
  return <ErrorBoundary scope={scope}>{children}</ErrorBoundary>;
}
