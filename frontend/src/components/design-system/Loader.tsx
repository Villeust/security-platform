import { LoadingOutlined } from '@ant-design/icons';
import { Skeleton, Spin } from 'antd';

type LoaderProps = {
  label?: string;
};

export function Loader({ label = 'Loading' }: LoaderProps) {
  return (
    <div className="sp-loader" aria-live="polite" aria-busy="true">
      <Spin indicator={<LoadingOutlined spin />} />
      <span>{label}</span>
    </div>
  );
}

export function PageLoader({ label = 'Загрузка раздела' }: LoaderProps) {
  return <Loader label={label} />;
}

export function InlineLoader({ label = 'Загрузка' }: LoaderProps) {
  return <Loader label={label} />;
}

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="sp-loading-grid" aria-live="polite" aria-busy="true">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} active paragraph={{ rows: 3 }} />
      ))}
    </div>
  );
}

export function ButtonLoader() {
  return <LoadingOutlined spin aria-label="Загрузка" />;
}
