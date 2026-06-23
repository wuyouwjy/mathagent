// ============================================================
// pages/BenchmarkCenter.tsx — Benchmark 评测中心
// ============================================================
import React, { useEffect, useState, useCallback } from 'react';
import { Card, Button, Progress, Statistic, Row, Col, Typography, Tag, Space, Table } from 'antd';
import { PlayCircleOutlined, StopOutlined, ReloadOutlined, BarChartOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { BarChart, PieChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import {
  fetchBenchmarkStatus, startBenchmark, stopBenchmark, getBenchmarkResults,
} from '../api/benchmark';
import type { BenchmarkStatus, BenchmarkResult } from '../types';
import { usePolling } from '../hooks/usePolling';
import { formatMs, getDomainCn } from '../utils';

echarts.use([BarChart, PieChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer]);

const { Title, Text } = Typography;

const BenchmarkCenter: React.FC = () => {
  const [status, setStatus] = useState<BenchmarkStatus | null>(null);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const s = await fetchBenchmarkStatus();
      setStatus(s);
      if (!s.running && s.progress > 0) {
        try {
          const r = await getBenchmarkResults();
          setResult(r);
        } catch {}
      }
    } catch {}
  }, []);

  usePolling(loadStatus, 2000, status?.running || false);

  useEffect(() => { loadStatus(); }, []);

  const handleStart = async () => {
    setLoading(true);
    try {
      await startBenchmark({ max_retries: 3, enable_rag: true });
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    await stopBenchmark();
    await loadStatus();
  };

  // ECharts 领域正确率柱状图
  const barChartOption = React.useMemo(() => {
    if (!result?.domain_accuracy) return {};
    const entries = Object.entries(result.domain_accuracy);
    return {
      tooltip: { trigger: 'axis', formatter: (p: { value: number }[]) => `${p[0].value.toFixed(2)}%` },
      xAxis: {
        type: 'category',
        data: entries.map(([k]) => getDomainCn(k) || k),
        axisLabel: { color: '#8899b4', rotate: 45, fontSize: 10 },
      },
      yAxis: { type: 'value', axisLabel: { color: '#8899b4', formatter: '{value}%' } },
      series: [{
        type: 'bar',
        data: entries.map(([, v]) => +(v * 100).toFixed(1)),
        itemStyle: { color: '#4f8cff', borderRadius: [6, 6, 0, 0] },
      }],
      grid: { bottom: 80 },
    };
  }, [result]);

  const pieChartOption = React.useMemo(() => {
    if (!result) return {};
    return {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['50%', '75%'],
        data: [
          { name: '正确', value: result.solved, itemStyle: { color: '#10b981' } },
          { name: '失败', value: result.failed, itemStyle: { color: '#ef4444' } },
        ],
        label: { color: '#8899b4' },
      }],
    };
  }, [result]);

  const progress = status ? ((status.progress / Math.max(status.total, 1)) * 100).toFixed(1) : 0;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ color: '#e0e6f0', margin: 0 }}>
          <BarChartOutlined style={{ marginRight: 8, color: '#10b981' }} />
          Benchmark 评测中心
        </Title>
        <Space>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart} loading={loading} disabled={status?.running}>
            一键运行评测
          </Button>
          <Button icon={<StopOutlined />} onClick={handleStop} disabled={!status?.running} danger>
            停止
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadStatus}>刷新</Button>
        </Space>
      </div>

      {/* 运行状态 */}
      {status?.running && (
        <Card style={{ marginBottom: 16, background: '#111827', borderColor: '#1e2d4a' }}>
          <Row gutter={16}>
            <Col span={8}>
              <Statistic title="进度" value={`${status.progress} / ${status.total}`} valueStyle={{ color: '#4f8cff' }} />
            </Col>
            <Col span={8}>
              <Statistic title="已用时间" value={formatMs(status.elapsed_seconds * 1000)} valueStyle={{ color: '#f59e0b' }} />
            </Col>
            <Col span={8}>
              <Statistic
                title="预估剩余"
                value={status.estimated_remaining_seconds ? formatMs(status.estimated_remaining_seconds * 1000) : '计算中...'}
                valueStyle={{ color: '#8b5cf6' }}
              />
            </Col>
          </Row>
          <Progress percent={+progress} status="active" style={{ marginTop: 16 }} />
          {status.current_question && (
            <div style={{ marginTop: 8 }}>
              <Text style={{ color: '#8899b4' }}>当前求解: </Text>
              <Tag color="blue">{status.current_question}</Tag>
            </div>
          )}
        </Card>
      )}

      {/* 结果显示 */}
      {result && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="总题数" value={result.total} valueStyle={{ color: '#e0e6f0' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="正确" value={result.solved} valueStyle={{ color: '#10b981' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="失败" value={result.failed} valueStyle={{ color: '#ef4444' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="正确率" value={`${result.accuracy}%`} valueStyle={{ color: '#4f8cff' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="平均置信度" value={result.avg_confidence.toFixed(3)} valueStyle={{ color: '#f59e0b' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="平均每题" value={formatMs(result.avg_time_per_question_ms)} valueStyle={{ color: '#8b5cf6' }} />
              </Card>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={14}>
              <Card title="领域正确率分布" style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <ReactEChartsCore echarts={echarts} option={barChartOption} style={{ height: 400 }} />
              </Card>
            </Col>
            <Col span={10}>
              <Card title="成功率饼图" style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <ReactEChartsCore echarts={echarts} option={pieChartOption} style={{ height: 400 }} />
              </Card>
            </Col>
          </Row>

          <Card title="耗时分布 (Top 20)" style={{ marginTop: 16, background: '#111827', borderColor: '#1e2d4a' }}>
            <Table
              dataSource={result.results?.slice(0, 20)}
              rowKey="question_id"
              size="small"
              pagination={false}
              columns={[
                { title: 'ID', dataIndex: 'question_id', width: 100, ellipsis: true },
                { title: '领域', dataIndex: 'domain', width: 120, render: (d: string) => <Tag color="blue">{getDomainCn(d) || d}</Tag> },
                { title: '答案', dataIndex: 'final_answer', ellipsis: true, render: (t: string) => <span style={{ color: '#c0d0e8' }}>{t?.substring(0, 60)}</span> },
                { title: '验证', dataIndex: ['verification', 'is_correct'], width: 80, render: (v: boolean) => v ? <Tag color="green">✅</Tag> : <Tag color="red">❌</Tag> },
                { title: '置信度', dataIndex: ['verification', 'confidence'], width: 90, render: (v: number) => v?.toFixed(3) },
                { title: '耗时', dataIndex: 'computation_time_ms', width: 100, render: (v: number) => formatMs(v) },
              ]}
            />
          </Card>
        </>
      )}

      {!status?.running && !result && (
        <Card style={{ background: '#111827', borderColor: '#1e2d4a', textAlign: 'center', padding: 60 }}>
          <BarChartOutlined style={{ fontSize: 48, color: '#4f8cff', marginBottom: 16 }} />
          <br />
          <Text style={{ color: '#8899b4', fontSize: 16 }}>
            点击「一键运行评测」对112道数学题进行自动评测
          </Text>
        </Card>
      )}
    </div>
  );
};

export default BenchmarkCenter;
