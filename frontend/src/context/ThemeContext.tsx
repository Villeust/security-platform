import { createContext, useContext, type PropsWithChildren } from 'react';
import { ConfigProvider, theme, type ThemeConfig } from 'antd';

type ThemeContextValue = {
  appName: string;
  mode: 'light';
};

const appTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#1677ff',
    colorSuccess: '#2f9e44',
    colorWarning: '#f59f00',
    colorError: '#d9480f',
    colorInfo: '#1677ff',
    colorTextBase: '#20242a',
    colorBgBase: '#f7f8fa',
    borderRadius: 6,
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  components: {
    Layout: {
      headerBg: '#ffffff',
      siderBg: '#111827',
      bodyBg: '#f7f8fa',
    },
    Card: {
      borderRadiusLG: 6,
    },
    Button: {
      borderRadius: 6,
    },
  },
};

const ThemeContext = createContext<ThemeContextValue>({
  appName: 'Security Platform',
  mode: 'light',
});

export function ThemeProvider({ children }: PropsWithChildren) {
  const value: ThemeContextValue = {
    appName: 'Security Platform',
    mode: 'light',
  };

  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider theme={appTheme}>{children}</ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useAppTheme() {
  return useContext(ThemeContext);
}
