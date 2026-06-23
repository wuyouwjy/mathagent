import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import router from './router';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#4f8cff',
          colorBgBase: '#0a0e17',
          colorBgContainer: '#111827',
          colorBgElevated: '#1a2236',
          colorBorder: '#1e2d4a',
          colorText: '#e0e6f0',
          colorTextSecondary: '#8899b4',
          borderRadius: 8,
          fontFamily: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`,
        },
        components: {
          Menu: {
            darkItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(79,140,255,0.15)',
            darkItemSelectedColor: '#4f8cff',
          },
          Card: {
            colorBgContainer: '#111827',
          },
          Table: {
            colorBgContainer: '#111827',
            borderColor: '#1e2d4a',
          },
          Input: {
            colorBgContainer: '#0a0e17',
          },
        },
      }}
    >
      <RouterProvider router={router} />
    </ConfigProvider>
  </React.StrictMode>
);
