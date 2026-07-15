import { Input } from 'antd';

type SearchBarProps = {
  placeholder?: string;
  onSearch?: (value: string) => void;
};

export function SearchBar({ placeholder = 'Search', onSearch }: SearchBarProps) {
  return <Input.Search allowClear placeholder={placeholder} onSearch={onSearch} className="sp-search-bar" />;
}
