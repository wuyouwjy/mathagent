// ============================================================
// components/WorkflowGraph.tsx — LangGraph 工作流可视化
// 使用 ECharts 绘制 Agent 节点流程图，支持当前节点高亮
// ============================================================
import React, { useMemo } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { GraphChart } from 'echarts/charts';
import { TooltipComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([GraphChart, TooltipComponent, CanvasRenderer]);

interface WorkflowGraphProps {
  activeNode?: string | null;
  nodeTrace?: string[];
  height?: number;
}

// LangGraph 工作流节点定义
const NODES = [
  { id: 'cache_check', label: 'Cache\nCheck', color: '#6366f1', category: 0 },
  { id: 'problem_parser', label: 'Problem\nParser', color: '#3b82f6', category: 1 },
  { id: 'classifier', label: 'Classifier', color: '#8b5cf6', category: 1 },
  { id: 'rag_retrieval', label: 'RAG\nRetrieval', color: '#06b6d4', category: 2 },
  { id: 'solver_dispatcher', label: 'Solver', color: '#10b981', category: 1 },
  { id: 'verifier', label: 'Verifier', color: '#f59e0b', category: 1 },
  { id: 'reflection', label: 'Reflection', color: '#ef4444', category: 3 },
  { id: 'formatter', label: 'Formatter', color: '#ec4899', category: 1 },
  { id: 'cache_save', label: 'Cache\nSave', color: '#6366f1', category: 0 },
  { id: 'error_handler', label: 'Error\nHandler', color: '#dc2626', category: 4 },
] as const;

const LINKS = [
  { source: 'cache_check', target: 'problem_parser', label: 'miss' },
  { source: 'cache_check', target: 'formatter', label: 'hit' },
  { source: 'problem_parser', target: 'classifier' },
  { source: 'classifier', target: 'rag_retrieval', label: 'ok' },
  { source: 'classifier', target: 'error_handler', label: 'fail' },
  { source: 'rag_retrieval', target: 'solver_dispatcher' },
  { source: 'solver_dispatcher', target: 'verifier' },
  { source: 'verifier', target: 'reflection' },
  { source: 'reflection', target: 'solver_dispatcher', label: 'retry' },
  { source: 'reflection', target: 'formatter', label: 'done' },
  { source: 'formatter', target: 'cache_save' },
];

const WorkflowGraph: React.FC<WorkflowGraphProps> = ({
  activeNode,
  nodeTrace = [],
  height = 400,
}) => {
  const option = useMemo(() => {
    const tracedIds = new Set(nodeTrace.map((t) => {
      const name = t.split('(')[0].split(':')[0].trim();
      return name;
    }));

    return {
      tooltip: {
        trigger: 'item',
        formatter: (p: { name: string }) => {
          const node = NODES.find((n) => n.id === p.name);
          const isActive = p.name === activeNode;
          const isTraced = tracedIds.has(p.name);
          const status = isActive ? '⚡ 执行中' : isTraced ? '✅ 已完成' : '⏳ 等待中';
          return `<b>${node?.label?.replace('\n', ' ') || p.name}</b><br/>${status}`;
        },
        backgroundColor: '#1a2236',
        borderColor: '#2d3a54',
        textStyle: { color: '#e0e6f0' },
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          force: {
            repulsion: 400,
            edgeLength: [120, 200],
            gravity: 0.15,
          },
          roam: false,
          draggable: false,
          data: NODES.map((n) => {
            const isActive = n.id === activeNode;
            const isTraced = tracedIds.has(n.id);
            return {
              id: n.id,
              name: n.id,
              symbolSize: isActive ? 70 : isTraced ? 60 : 50,
              itemStyle: {
                color: n.color,
                borderColor: isActive ? '#fff' : isTraced ? `${n.color}80` : 'transparent',
                borderWidth: isActive ? 3 : isTraced ? 2 : 0,
                shadowBlur: isActive ? 20 : isTraced ? 8 : 0,
                shadowColor: isActive ? n.color : 'transparent',
                opacity: isTraced || isActive ? 1 : 0.5,
              },
              label: {
                show: true,
                formatter: n.label,
                color: isActive ? '#fff' : isTraced ? '#c0d0e8' : '#5a6d8a',
                fontSize: 10,
                fontWeight: isActive ? 'bold' : 'normal',
              },
            };
          }),
          links: LINKS.map((l) => ({
            source: l.source,
            target: l.target,
            lineStyle: {
              color: '#2d3a54',
              width: 1,
              curveness: 0.2,
              opacity: 0.6,
            },
            label: {
              show: !!l.label,
              formatter: l.label,
              color: '#5a6d8a',
              fontSize: 9,
            },
          })),
          emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 3 },
          },
          categories: [
            { name: '缓存' },
            { name: '核心' },
            { name: '检索' },
            { name: '控制' },
            { name: '错误' },
          ],
        },
      ],
    };
  }, [activeNode, nodeTrace]);

  return (
    <ReactEChartsCore
      echarts={echarts}
      option={option}
      style={{ height, width: '100%' }}
      notMerge
      lazyUpdate
      opts={{ renderer: 'canvas' }}
    />
  );
};

export default WorkflowGraph;
