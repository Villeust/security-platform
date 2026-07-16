import { Table as AntTable, type TableProps as AntTableProps } from 'antd';

export type TableProps<T extends object> = AntTableProps<T>;

export function Table<T extends object>(props: TableProps<T>) {
  const className = ['sp-data-table', props.className].filter(Boolean).join(' ');
  return <AntTable<T> pagination={false} scroll={{ x: 'max-content', ...props.scroll }} {...props} className={className} />;
}
