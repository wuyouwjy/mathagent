// ============================================================
// pages/ResultAnalysis.tsx — 结果分析中心 (重点)
// ============================================================
import React, { useEffect, useState } from 'react';
import { Card, Select, Typography, Collapse, Empty, Spin, Tag, Row, Col, Statistic } from 'antd';
import { PieChartOutlined, CodeOutlined } from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { PieChart, BarChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { fetchProblems } from '../api/problems';
import type { Problem } from '../types';
import { getDomainCn } from '../utils';
import ReasoningTree from '../components/ReasoningTree';
import JsonViewer from '../components/JsonViewer';
import LatexRenderer from '../components/LatexRenderer';

echarts.use([PieChart, BarChart, TooltipComponent, LegendComponent, TitleComponent, CanvasRenderer]);

const { Title, Text } = Typography;

const ResultAnalysis: React.FC = () => {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadProblems();
  }, []);

  const loadProblems = async () => {
    setLoading(true);
    try {
      const res = await fetchProblems({ page: 1, page_size: 200 });
      setProblems(res.items.filter((p) => p.status === 'solved' || p.status === 'failed'));
    } finally {
      setLoading(false);
    }
  };

  const selected = problems.find((p) => p.id === selectedId);

  // 领域分布饼图
  const domainPieOption = React.useMemo(() => {
    const dist: Record<string, number> = {};
    problems.forEach((p) => {
      const cn = getDomainCn(p.domain) || p.domain || '未知';
      dist[cn] = (dist[cn] || 0) + 1;
    });
    return {
      tooltip: { trigger: 'item' },
      legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { color: '#8899b4' } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        data: Object.entries(dist).map(([name, value]) => ({ name, value })),
        label: { color: '#8899b4', fontSize: 10 },
        itemStyle: { borderColor: '#0a0e17', borderWidth: 2 },
      }],
    };
  }, [problems]);

  // 置信度分布柱状图
  const confidenceBarOption = React.useMemo(() => {
    const ranges = ['0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0'];
    const counts = [0, 0, 0, 0, 0];
    problems.forEach((p) => {
      const c = p.verification?.confidence || 0;
      const idx = Math.min(Math.floor(c / 0.2), 4);
      counts[idx]++;
    });
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: ranges, axisLabel: { color: '#8899b4' } },
      yAxis: { type: 'value', axisLabel: { color: '#8899b4' } },
      series: [{
        type: 'bar', data: counts,
        itemStyle: { color: '#4f8cff', borderRadius: [6, 6, 0, 0] },
      }],
    };
  }, [problems]);

  return (
    <div>
      <Title level={4} style={{ color: '#e0e6f0', margin: 0, marginBottom: 16 }}>
        <PieChartOutlined style={{ marginRight: 8, color: '#ec4899' }} />
        结果分析中心
      </Title>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="领域分布" style={{ background: '#111827', borderColor: '#1e2d4a' }}>
            <ReactEChartsCore echarts={echarts} option={domainPieOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="置信度分布" style={{ background: '#111827', borderColor: '#1e2d4a' }}>
            <ReactEChartsCore echarts={echarts} option={confidenceBarOption} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>

      {/* 单个结果分析 */}
      <Card
        title={<span><CodeOutlined /> 求解结果详情</span>}
        style={{ marginTop: 16, background: '#111827', borderColor: '#1e2d4a' }}
      >
        <div style={{ marginBottom: 16 }}>
          <Select
            showSearch
            placeholder="选择已求解的问题"
            value={selectedId}
            onChange={setSelectedId}
            style={{ width: 400 }}
            loading={loading}
            options={problems.map((p) => ({
              label: `[${p.id}] ${p.question_text?.substring(0, 60)}...`,
              value: p.id,
            }))}
            filterOption={(input, option) =>
              (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
            }
          />
        </div>

        {!selected ? (
          <Empty description="请选择一个已求解的问题" />
        ) : (
          <div style={{ color: '#e0e6f0' }}>
            {/* 基本信息 */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}><Statistic title="答案" value={selected.final_answer?.substring(0, 30) || '-'} valueStyle={{ color: '#10b981', fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="置信度" value={selected.verification?.confidence?.toFixed(4)} valueStyle={{ color: '#4f8cff', fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="耗时" value={`${selected.computation_time_ms?.toFixed(0) || '-'}ms`} valueStyle={{ color: '#f59e0b', fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="方法数" value={selected.methods_used?.length || 0} valueStyle={{ color: '#8b5cf6', fontSize: 18 }} /></Col>
            </Row>

            <Collapse
              defaultActiveKey={['answer', 'reasoning']}
              items={[
                {
                  key: 'answer',
                  label: <Text style={{ color: '#4f8cff' }}>✅ 最终答案 (LaTeX)</Text>,
                  children: <LatexRenderer content={selected.final_answer || ''} />,
                },
                {
                  key: 'reasoning',
                  label: <Text style={{ color: '#4f8cff' }}>🧠 推理过程 ({selected.reasoning_steps?.length || 0} 步)</Text>,
                  children: selected.reasoning_steps?.length ? (
                    <ReasoningTree steps={selected.reasoning_steps} />
                  ) : <Text style={{ color: '#5a6d8a' }}>无推理步骤</Text>,
                },
                {
                  key: 'hint',
                  label: <Text style={{ color: '#4f8cff' }}>💡 教育提示</Text>,
                  children: <LatexRenderer content={selected.educational_hint || '无'} />,
                },
                {
                  key: 'json',
                  label: <Text style={{ color: '#4f8cff' }}>📄 完整 JSON</Text>,
                  children: selected.raw_output ? (
                    <JsonViewer data={selected.raw_output} />
                  ) : <Text style={{ color: '#5a6d8a' }}>无JSON数据</Text>,
                },
              ]}
            />
          </div>
        )}
      </Card>
    </div>
  );
};

export default ResultAnalysis;
