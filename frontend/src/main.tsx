import React from 'react';
import ReactDOM from 'react-dom/client';
import 'antd/dist/reset.css';

import { App } from './App';
import { ErrorBoundary } from './components/errors/ErrorBoundary';
import './styles/theme.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary scope="global">
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
