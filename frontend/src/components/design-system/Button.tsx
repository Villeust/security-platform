import { Button as AntButton, type ButtonProps as AntButtonProps } from 'antd';

export type ButtonProps = AntButtonProps;

export function Button(props: ButtonProps) {
  return <AntButton {...props} />;
}
