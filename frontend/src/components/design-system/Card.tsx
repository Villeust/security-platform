import { Card as AntCard, type CardProps as AntCardProps } from 'antd';

export type CardProps = AntCardProps;

export function Card(props: CardProps) {
  return <AntCard {...props} />;
}
