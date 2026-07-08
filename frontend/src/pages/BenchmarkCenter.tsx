// ============================================================
// pages/BenchmarkCenter.tsx — Benchmark 评测中心
// ============================================================
import React, { useEffect, useState, useCallback } from 'react';
import { Card, Button, Progress, Statistic, Row, Col, Typography, Tag, Space, Table, Switch, Steps, Collapse, Popconfirm, InputNumber } from 'antd';
import { PlayCircleOutlined, StopOutlined, ReloadOutlined, BarChartOutlined, DeleteOutlined, HistoryOutlined, CloseCircleOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { BarChart, PieChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import {
  fetchBenchmarkStatus, startBenchmark, stopBenchmark, getBenchmarkResults, clearAnswerDb,
  fetchBenchmarkRuns, fetchBenchmarkRun, deleteBenchmarkRun,
} from '../api/benchmark';
import type { BenchmarkStatus, BenchmarkResult, BenchmarkRunSummary, BenchmarkRunRecord } from '../types';
import { usePolling } from '../hooks/usePolling';
import { formatMs, getDomainCn } from '../utils';

echarts.use([BarChart, PieChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer]);

const { Title, Text } = Typography;

const BenchmarkCenter: React.FC = () => {
  const [status, setStatus] = useState<BenchmarkStatus | null>(null);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [useAnswerDb, setUseAnswerDb] = useState(true);
  const [maxReflection, setMaxReflection] = useState(1);

  // 历史记录
  const [runs, setRuns] = useState<BenchmarkRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<BenchmarkRunRecord | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const s = await fetchBenchmarkStatus();
      setStatus(s);
      if (!s.running && s.progress > 0) {
        try {
          const r = await getBenchmarkResults();
          setResult(r);
        } catch {}
        // 刷新历史记录
        loadRuns();
      }
    } catch {}
  }, []);

  const loadRuns = async () => {
    try {
      const list = await fetchBenchmarkRuns();
      setRuns(list);
    } catch {}
  };

  usePolling(loadStatus, 1000, status?.running || false);

  useEffect(() => { loadStatus(); loadRuns(); }, []);

  const handleStart = async () => {
    setLoading(true);
    setResult(null);
    setSelectedRun(null);
    try {
      await startBenchmark({ max_retries: 3, enable_rag: true, use_answer_db: useAnswerDb, max_reflection_count: maxReflection });
      await loadStatus();
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    await stopBenchmark();
    await loadStatus();
  };

  const handleClearDb = async () => {
    try {
      await clearAnswerDb();
    } catch {}
  };

  const handleViewRun = async (runId: string) => {
    setHistoryLoading(true);
    try {
      const record = await fetchBenchmarkRun(runId);
      setSelectedRun(record);
    } catch {} finally {
      setHistoryLoading(false);
    }
  };

  const handleDeleteRun = async (runId: string) => {
    try {
      await deleteBenchmarkRun(runId);
      await loadRuns();
      if (selectedRun?.run_id === runId) setSelectedRun(null);
    } catch {}
  };

  // ECharts 领域正确率柱状图
  const barChartOption = React.useMemo(() => {
    const data = selectedRun?.domain_stats || result?.domain_accuracy;
    if (!data) return {};
    const entries = Array.isArray(data) ? [] : Object.entries(data);
    if (entries.length === 0) return {};
    const isOldFormat = typeof entries[0]?.[1] === 'number';
    return {
      tooltip: { trigger: 'axis', formatter: (p: { value: number }[]) => `${p[0].value.toFixed(1)}%` },
      xAxis: {
        type: 'category',
        data: entries.map(([k]) => getDomainCn(k) || k),
        axisLabel: { color: '#8899b4', rotate: 45, fontSize: 10 },
      },
      yAxis: { type: 'value', axisLabel: { color: '#8899b4', formatter: '{value}%' } },
      series: [{
        type: 'bar',
        data: entries.map(([, v]) => isOldFormat ? +(v * 100).toFixed(1) : +(v as any).accuracy || 0),
        itemStyle: { color: '#4f8cff', borderRadius: [6, 6, 0, 0] },
      }],
      grid: { bottom: 80 },
    };
  }, [result, selectedRun]);

  const pieChartOption = React.useMemo(() => {
    const r = selectedRun || result;
    if (!r) return {};
    return {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['50%', '75%'],
        data: [
          { name: '正确', value: r.solved, itemStyle: { color: '#10b981' } },
          { name: '失败', value: (r as any).failed || (r.total - r.solved), itemStyle: { color: '#ef4444' } },
        ],
        label: { color: '#8899b4' },
      }],
    };
  }, [result, selectedRun]);

  const progress = status ? ((status.progress / Math.max(status.total, 1)) * 100).toFixed(1) : 0;

  // 实时 trace 转 Steps
  const traceSteps = (status?.current_trace || []).map((t, i) => ({
    title: t,
    status: i === (status?.current_trace?.length || 0) - 1 ? 'process' : 'finish',
  }));

  // 错题列表（优先用 selectedRun 的数据）
  const wrongList = selectedRun?.wrong_questions || result?.results
    ?.filter(r => !r.verification?.is_correct)
    .map(r => ({
      question_id: r.question_id,
      domain: r.domain,
      predicted: r.final_answer?.substring(0, 100) || '',
      ground_truth: (r as any).ground_truth || '',
      time_ms: r.computation_time_ms,
    })) || [];

  const displayData = selectedRun || result;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ color: '#e0e6f0', margin: 0 }}>
          <BarChartOutlined style={{ marginRight: 8, color: '#10b981' }} />
          Benchmark 评测中心
        </Title>
        <Space>
          <span style={{ color: '#8899b4', fontSize: 13 }}>
            <Switch
              checked={useAnswerDb}
              onChange={setUseAnswerDb}
              disabled={status?.running}
              size="small"
              style={{ marginRight: 6 }}
            />
            正确答案库
          </span>
          <span style={{ color: '#8899b4', fontSize: 13 }}>
            反思次数
            <InputNumber
              min={0}
              max={5}
              value={maxReflection}
              onChange={(v) => setMaxReflection(v ?? 1)}
              disabled={status?.running}
              size="small"
              style={{ width: 50, marginLeft: 6 }}
            />
          </span>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart} loading={loading} disabled={status?.running}>
            一键运行评测
          </Button>
          <Button icon={<StopOutlined />} onClick={handleStop} disabled={!status?.running} danger>
            停止
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadStatus}>刷新</Button>
          <Button icon={<DeleteOutlined />} onClick={handleClearDb} disabled={status?.running}>清空数据库</Button>
        </Space>
      </div>

      {/* 运行中 */}
      {status?.running && (
        <>
          <Card style={{ marginBottom: 16, background: '#111827', borderColor: '#4f8cff' }}>
            <div style={{ textAlign: 'center', marginBottom: 16 }}>
              <Title level={5} style={{ color: '#4f8cff', margin: 0 }}>正在评测中…</Title>
            </div>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic title="已算完" value={`${status.progress} / ${status.total}`} valueStyle={{ color: '#4f8cff', fontSize: 28 }} />
              </Col>
              <Col span={6}>
                <Statistic title="答对数" value={status.solved} valueStyle={{ color: '#10b981', fontSize: 28 }} />
              </Col>
              <Col span={6}>
                <Statistic title="当前准确率" value={status.progress > 0 ? `${((status.solved / status.progress) * 100).toFixed(1)}%` : '--'} valueStyle={{ color: '#f59e0b', fontSize: 28 }} />
              </Col>
              <Col span={6}>
                <Statistic title="已用时" value={formatMs(status.elapsed_seconds * 1000)} valueStyle={{ color: '#8b5cf6', fontSize: 20 }} />
              </Col>
            </Row>
            <Progress percent={+progress} status="active" strokeColor="#4f8cff" style={{ marginTop: 16 }} />
            {status.current_question && (
              <div style={{ marginTop: 8, textAlign: 'center' }}>
                <Text style={{ color: '#8899b4' }}>正在解: </Text>
                <Tag color="blue">{status.current_question}</Tag>
              </div>
            )}
          </Card>

          {/* 实时求解流程 */}
          {traceSteps.length > 0 && (
            <Card title="📋 当前题目求解流程" style={{ marginBottom: 16, background: '#111827', borderColor: '#1e2d4a' }}>
              <Steps
                direction="vertical"
                size="small"
                current={traceSteps.length - 1}
                items={traceSteps.map(s => ({
                  title: <span style={{ color: s.status === 'process' ? '#4f8cff' : '#8899b4', fontSize: 13 }}>{s.title}</span>,
                  status: s.status === 'process' ? 'process' : 'finish',
                }))}
              />
            </Card>
          )}
        </>
      )}

      {/* 结果显示 */}
      {displayData && !status?.running && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="总题数" value={displayData.total} valueStyle={{ color: '#e0e6f0' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="正确" value={displayData.solved} valueStyle={{ color: '#10b981' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="失败" value={(displayData as any).failed || (displayData.total - displayData.solved)} valueStyle={{ color: '#ef4444' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="正确率" value={`${displayData.accuracy}%`} valueStyle={{ color: '#4f8cff' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="平均每题" value={formatMs((displayData as any).avg_time_per_question_ms || 0)} valueStyle={{ color: '#8b5cf6' }} />
              </Card>
            </Col>
            <Col span={4}>
              <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
                <Statistic title="总耗时" value={formatMs((displayData as any).total_time_ms || 0)} valueStyle={{ color: '#f59e0b' }} />
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

          {/* 错题列表 */}
          {wrongList.length > 0 && (
            <Card
              title={<span><CloseCircleOutlined style={{ color: '#ef4444', marginRight: 8 }} />错题列表 ({wrongList.length}题)</span>}
              style={{ marginTop: 16, background: '#111827', borderColor: '#ef4444' }}
            >
              <Table
                dataSource={wrongList}
                rowKey="question_id"
                size="small"
                pagination={{ pageSize: 15, size: 'small' }}
                columns={[
                  { title: '题号', dataIndex: 'question_id', width: 90 },
                  { title: '领域', dataIndex: 'domain', width: 120, render: (d: string) => <Tag color="blue">{getDomainCn(d) || d}</Tag> },
                  { title: '预测答案', dataIndex: 'predicted', ellipsis: true, render: (t: string) => <span style={{ color: '#f87171' }}>{t}</span> },
                  { title: '标准答案', dataIndex: 'ground_truth', ellipsis: true, render: (t: string) => <span style={{ color: '#10b981' }}>{t}</span> },
                  { title: '耗时', dataIndex: 'time_ms', width: 100, render: (v: number) => formatMs(v) },
                ]}
              />
            </Card>
          )}
        </>
      )}

      {/* 历史记录 */}
      <Card
        title={<span><HistoryOutlined style={{ color: '#4f8cff', marginRight: 8 }} />评测历史记录</span>}
        style={{ marginTop: 16, background: '#111827', borderColor: '#1e2d4a' }}
      >
        {runs.length === 0 ? (
          <Text style={{ color: '#8899b4' }}>暂无评测记录，运行一次评测后这里会出现记录</Text>
        ) : (
          <Collapse
            accordion
            onChange={(keys) => {
              const key = Array.isArray(keys) ? keys[0] : keys;
              if (key) handleViewRun(String(key));
              else setSelectedRun(null);
            }}
            style={{ background: 'transparent' }}
            items={runs.map(run => ({
              key: run.run_id,
              label: (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <Space>
                    <Tag color={run.status === 'completed' ? 'green' : run.status === 'interrupted' ? 'orange' : 'blue'}>
                      {run.status === 'completed' ? '已完成' : run.status === 'interrupted' ? '中断' : run.status}
                    </Tag>
                    <Text style={{ color: '#c0d0e8' }}>{run.run_id}</Text>
                  </Space>
                  <Space>
                    <Text style={{ color: '#8899b4', fontSize: 12 }}>{run.started_at?.substring(0, 19).replace('T', ' ')}</Text>
                    <Text style={{ color: '#4f8cff' }}>{run.solved}/{run.total}</Text>
                    <Text style={{ color: run.accuracy >= 50 ? '#10b981' : '#f59e0b', fontWeight: 'bold' }}>{run.accuracy}%</Text>
                    <Text style={{ color: '#8899b4', fontSize: 12 }}>{formatMs(run.total_time_ms)}</Text>
                  </Space>
                </div>
              ),
              extra: (
                <Popconfirm
                  title="确认删除这条记录？"
                  onConfirm={(e) => { e?.stopPropagation(); handleDeleteRun(run.run_id); }}
                  onCancel={(e) => e?.stopPropagation()}
                >
                  <Button
                    size="small"
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              ),
              children: selectedRun && selectedRun.run_id === run.run_id ? (
                historyLoading ? (
                  <Text style={{ color: '#8899b4' }}>加载中…</Text>
                ) : (
                  <div>
                    <Row gutter={16} style={{ marginBottom: 12 }}>
                      <Col span={8}><Text style={{ color: '#8899b4' }}>数据集: {selectedRun.dataset}</Text></Col>
                      <Col span={8}><Text style={{ color: '#8899b4' }}>完成时间: {selectedRun.completed_at?.substring(0, 19).replace('T', ' ') || '-'}</Text></Col>
                      <Col span={8}><Text style={{ color: '#8899b4' }}>平均每题: {formatMs(selectedRun.avg_time_per_question_ms)}</Text></Col>
                    </Row>
                    {selectedRun.wrong_questions?.length > 0 && (
                      <Text style={{ color: '#ef4444', fontSize: 12 }}>
                        错题: {selectedRun.wrong_questions.map(w => w.question_id).join(', ')}
                      </Text>
                    )}
                    {selectedRun.domain_stats && Object.keys(selectedRun.domain_stats).length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        {Object.entries(selectedRun.domain_stats).map(([d, s]) => (
                          <Tag key={d} color={s.accuracy >= 50 ? 'green' : 'red'} style={{ marginBottom: 4 }}>
                            {getDomainCn(d) || d}: {s.solved}/{s.total} ({s.accuracy}%)
                          </Tag>
                        ))}
                      </div>
                    )}
                  </div>
                )
              ) : null,
            }))}
          />
        )}
      </Card>

      {!status?.running && !result && runs.length === 0 && (
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
