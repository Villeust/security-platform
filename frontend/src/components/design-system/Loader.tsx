import { Spin } from 'antd';

type LoaderProps = {
  label?: string;
};

export function Loader({ label = 'Loading' }: LoaderProps) {
  return (
    <div className="sp-loader">
      <Spin />
      <span>{label}</span>
    </div>
  );
}
