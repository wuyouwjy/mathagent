// ============================================================
// components/ProblemDrawer.tsx — 问题详情抽屉
// ============================================================
import React from 'react';
import { Drawer, Descriptions, Tag, Divider, Collapse, Typography, Empty, Spin } from 'antd';
import { CodeOutlined } from '@ant-design/icons';
import type { Problem } from '../types';
import { getDomainCn, getStatusColor, getDifficultyColor } from '../utils';
import ReasoningTree from './ReasoningTree';
import JsonViewer from './JsonViewer';
import LatexRenderer from './LatexRenderer';

const { Text, Title } = Typography;

interface ProblemDrawerProps {
  open: boolean;
  problem: Problem | null;
  loading: boolean;
  onClose: () => void;
}

const ProblemDrawer: React.FC<ProblemDrawerProps> = ({ open, problem, loading, onClose }) => (
  <Drawer
    title={
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <CodeOutlined />
        <span>问题详情</span>
      </div>
    }
    placement="right"
    width={680}
    open={open}
    onClose={onClose}
    styles={{
      header: { background: '#0d1321', borderBottom: '1px solid #1e2d4a' },
      body: { background: '#0a0e17', padding: 24 },
    }}
  >
    {loading ? (
      <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
    ) : !problem ? (
      <Empty description="请选择一个问题" />
    ) : (
      <div style={{ color: '#e0e6f0' }}>
        {/* 基本信息 */}
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="ID">{problem.id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={getStatusColor(problem.status)}>{problem.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="领域">
            {getDomainCn(problem.domain) || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="难度">
            <Tag color={getDifficultyColor(problem.difficulty)}>{problem.difficulty}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间" span={2}>
            {problem.created_at}
          </Descriptions.Item>
        </Descriptions>

        <Divider />

        {/* 原题 */}
        <Title level={5} style={{ color: '#c0d0e8' }}>📝 原题</Title>
        <div
          style={{
            background: '#111827',
            padding: 16,
            borderRadius: 8,
            border: '1px solid #1e2d4a',
            whiteSpace: 'pre-wrap',
            lineHeight: 1.8,
          }}
        >
          <LatexRenderer content={problem.question_text} />
        </div>

        {problem.final_answer && (
          <>
            <Divider />
            <Title level={5} style={{ color: '#c0d0e8' }}>✅ 最终答案</Title>
            <div
              style={{
                background: 'linear-gradient(135deg, #0d2818 0%, #111827 100%)',
                padding: 16,
                borderRadius: 8,
                border: '1px solid #1e3a2a',
              }}
            >
              <LatexRenderer content={problem.final_answer} />
            </div>
          </>
        )}

        {problem.reasoning_steps && problem.reasoning_steps.length > 0 && (
          <>
            <Divider />
            <Title level={5} style={{ color: '#c0d0e8' }}>🧠 推理过程</Title>
            <ReasoningTree steps={problem.reasoning_steps} />
          </>
        )}

        {problem.methods_used && problem.methods_used.length > 0 && (
          <>
            <Divider />
            <Title level={5} style={{ color: '#c0d0e8' }}>🔧 使用的方法</Title>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {problem.methods_used.map((m, i) => (
                <Tag key={i} color="blue">{m}</Tag>
              ))}
            </div>
          </>
        )}

        {problem.educational_hint && (
          <>
            <Divider />
            <Title level={5} style={{ color: '#c0d0e8' }}>💡 教育提示</Title>
            <Text style={{ color: '#8899b4' }}>{problem.educational_hint}</Text>
          </>
        )}

        {problem.raw_output && (
          <>
            <Divider />
            <Collapse
              ghost
              items={[
                {
                  key: 'json',
                  label: <Text style={{ color: '#4f8cff' }}>📄 完整 JSON 结果</Text>,
                  children: <JsonViewer data={problem.raw_output} />,
                },
              ]}
            />
          </>
        )}
      </div>
    )}
  </Drawer>
);

export default ProblemDrawer;
