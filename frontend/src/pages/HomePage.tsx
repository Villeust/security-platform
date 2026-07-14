import { useEffect, useState } from 'react';
import { Alert, Layout, Spin, Typography } from 'antd';

import { api } from '../services/api';

type HealthStatus = 'loading' | 'online' | 'offline';

export function HomePage() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('loading');

  useEffect(() => {
    api
      .get('/api/v1/health')
      .then(() => setHealthStatus('online'))
      .catch(() => setHealthStatus('offline'));
  }, []);

  return (
    <Layout style={{ minHeight: '100vh', padding: 32 }}>
      <Layout.Content style={{ maxWidth: 960, width: '100%', margin: '0 auto' }}>
        <Typography.Title level={1}>Contractor Requests</Typography.Title>
        {healthStatus === 'loading' ? (
          <Spin />
        ) : (
          <Alert
            message={healthStatus === 'online' ? 'Backend online' : 'Backend offline'}
            type={healthStatus === 'online' ? 'success' : 'error'}
            showIcon
          />
        )}
      </Layout.Content>
    </Layout>
  );
}
