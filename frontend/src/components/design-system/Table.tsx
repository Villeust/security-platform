import { Table as AntTable, type TableProps as AntTableProps } from 'antd';

export type TableProps<T extends object> = AntTableProps<T>;

export function Table<T extends object>(props: TableProps<T>) {
  return <AntTable<T> pagination={false} {...props} />;
}
