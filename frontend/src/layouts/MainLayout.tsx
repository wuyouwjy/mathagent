// ============================================================
// layouts/MainLayout.tsx — 主布局 (左侧菜单 + 内容区)
// ============================================================
import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Button, theme } from 'antd';
import {
  DashboardOutlined,
  BookOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  PieChartOutlined,
  BarChartOutlined,
  SettingOutlined,
  FileSearchOutlined,
  InfoCircleOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useAppStore } from '../stores';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '首页 Dashboard' },
  { key: '/problems', icon: <BookOutlined />, label: '数学问题库' },
  { key: '/agent', icon: <ThunderboltOutlined />, label: 'Agent 运行中心' },
  { key: '/tasks', icon: <FileTextOutlined />, label: '求解任务记录' },
  { key: '/analysis', icon: <PieChartOutlined />, label: '结果分析中心' },
  { key: '/benchmark', icon: <BarChartOutlined />, label: 'Benchmark 评测' },
  { key: '/config', icon: <SettingOutlined />, label: '系统配置' },
  { key: '/logs', icon: <FileSearchOutlined />, label: '日志中心' },
  { key: '/about', icon: <InfoCircleOutlined />, label: '关于系统' },
];

const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = useAppStore((s) => s.collapsed);
  const toggleCollapsed = useAppStore((s) => s.toggleCollapsed);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 左侧菜单栏 */}
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={240}
        style={{
          background: 'linear-gradient(180deg, #0a0e17 0%, #0d1321 100%)',
          borderRight: '1px solid #1e2d4a',
        }}
      >
        {/* Logo 区域 */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 16px',
            borderBottom: '1px solid #1e2d4a',
          }}
        >
          {!collapsed && (
            <div style={{ textAlign: 'center' }}>
              <Text
                strong
                style={{
                  color: '#4f8cff',
                  fontSize: 16,
                  letterSpacing: 1,
                }}
              >
                <ExperimentOutlined style={{ marginRight: 8 }} />
                Math-Agent
              </Text>
              <br />
              <Text style={{ color: '#5a6d8a', fontSize: 10 }}>
                AI 数学推理平台 v1.0
              </Text>
            </div>
          )}
          {collapsed && (
            <ThunderboltOutlined style={{ fontSize: 22, color: '#4f8cff' }} />
          )}
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: 'transparent',
            borderRight: 0,
            marginTop: 8,
          }}
        />
      </Sider>

      {/* 右侧内容区域 */}
      <Layout>
        <Header
          style={{
            background: '#0a0e17',
            borderBottom: '1px solid #1e2d4a',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 56,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={toggleCollapsed}
            style={{ fontSize: 16, color: '#8899b4' }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Text style={{ color: '#5a6d8a', fontSize: 13 }}>
              Math-Agent-System | 基于 LangGraph + Intern-S1
            </Text>
          </div>
        </Header>

        <Content
          style={{
            margin: 20,
            padding: 24,
            background: '#0d1321',
            borderRadius: 12,
            minHeight: 280,
            overflow: 'auto',
            border: '1px solid #1e2d4a',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
