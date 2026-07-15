import { Badge as AntBadge, type BadgeProps as AntBadgeProps } from 'antd';

export type BadgeProps = AntBadgeProps;

export function Badge(props: BadgeProps) {
  return <AntBadge {...props} />;
}
