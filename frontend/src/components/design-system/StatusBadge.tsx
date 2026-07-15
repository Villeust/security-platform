import { Tag } from 'antd';

type StatusTone = 'success' | 'processing' | 'warning' | 'error' | 'default';

type StatusBadgeProps = {
  label: string;
  tone?: StatusTone;
};

const toneColor: Record<StatusTone, string> = {
  success: 'success',
  processing: 'processing',
  warning: 'warning',
  error: 'error',
  default: 'default',
};

export function StatusBadge({ label, tone = 'default' }: StatusBadgeProps) {
  return <Tag color={toneColor[tone]}>{label}</Tag>;
}
