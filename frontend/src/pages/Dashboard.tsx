// ============================================================
// pages/Dashboard.tsx — 首页 Dashboard
// ============================================================
import React, { useEffect, useState } from 'react';
import { Row, Col, Card, Table, Tag, Typography, Spin } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import StatCard from '../components/StatCard';
import WorkflowGraph from '../components/WorkflowGraph';
import { fetchDashboardStats } from '../api/dashboard';
import { fetchProblems } from '../api/problems';
import type { DashboardStats, Problem } from '../types';
import { formatMs, getStatusColor } from '../utils';

const { Title } = Typography;

const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentProblems, setRecentProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [s, p] = await Promise.all([
        fetchDashboardStats(),
        fetchProblems({ page: 1, page_size: 10 }),
      ]);
      setStats(s);
      setRecentProblems(p.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const accuracyPct = stats ? ((stats.solved_count / Math.max(stats.total_problems, 1)) * 100).toFixed(1) : '0';

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ color: '#e0e6f0', margin: 0 }}>
          <ExperimentOutlined style={{ marginRight: 8, color: '#4f8cff' }} />
          系统概览
        </Title>
      </div>

      {/* 顶部统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="问题总数"
            value={stats?.total_problems || 0}
            suffix="题"
            icon={<BarChartOutlined />}
            color="#4f8cff"
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="成功求解"
            value={stats?.solved_count || 0}
            suffix="题"
            icon={<CheckCircleOutlined />}
            color="#10b981"
            loading={loading}
            trend="up"
            trendValue={`正确率 ${accuracyPct}%`}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="求解失败"
            value={stats?.failed_count || 0}
            suffix="题"
            icon={<CloseCircleOutlined />}
            color="#ef4444"
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="平均耗时"
            value={stats ? formatMs(stats.avg_time_ms) : '0ms'}
            icon={<ClockCircleOutlined />}
            color="#f59e0b"
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="平均正确率"
            value={(stats?.avg_accuracy || 0).toFixed(2)}
            suffix="%"
            icon={<ThunderboltOutlined />}
            color="#8b5cf6"
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatCard
            title="当前模型"
            value={stats?.current_model || '-'}
            icon={<ExperimentOutlined />}
            color="#ec4899"
            loading={loading}
          />
        </Col>
      </Row>

      {/* Agent 工作流图 */}
      <Card
        title="🧬 Agent 工作流拓扑"
        style={{ marginTop: 20, background: '#111827', borderColor: '#1e2d4a' }}
      >
        <WorkflowGraph height={380} />
      </Card>

      {/* 最近任务列表 */}
      <Card
        title="📋 最近任务"
        style={{ marginTop: 20, background: '#111827', borderColor: '#1e2d4a' }}
      >
        <Table
          dataSource={recentProblems}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={false}
          columns={[
            { title: 'ID', dataIndex: 'id', key: 'id', width: 100, ellipsis: true },
            {
              title: '问题',
              dataIndex: 'question_text',
              key: 'question_text',
              ellipsis: true,
              render: (t: string) => (
                <span style={{ color: '#c0d0e8' }}>{t?.substring(0, 60)}{t?.length > 60 ? '...' : ''}</span>
              ),
            },
            {
              title: '领域',
              dataIndex: 'domain',
              key: 'domain',
              width: 120,
              render: (d: string) => d ? <Tag color="blue">{d}</Tag> : '-',
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              width: 90,
              render: (s: string) => <Tag color={getStatusColor(s)}>{s}</Tag>,
            },
            {
              title: '创建时间',
              dataIndex: 'created_at',
              key: 'created_at',
              width: 170,
            },
          ]}
        />
      </Card>
    </div>
  );
};

export default Dashboard;
