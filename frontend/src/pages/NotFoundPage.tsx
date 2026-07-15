import { Result } from 'antd';
import { Link } from 'react-router-dom';

import { Button } from '../components/design-system';

export function NotFoundPage() {
  return (
    <Result
      status="404"
      title="404"
      subTitle="Page not found"
      extra={
        <Link to="/">
          <Button type="primary">Go home</Button>
        </Link>
      }
    />
  );
}
