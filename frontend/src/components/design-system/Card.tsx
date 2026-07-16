import { Card as AntCard, type CardProps as AntCardProps } from 'antd';

export type CardProps = AntCardProps;

export function Card(props: CardProps) {
  const className = ['sp-card', props.className].filter(Boolean).join(' ');
  return <AntCard {...props} className={className} />;
}
