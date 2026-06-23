// ============================================================
// components/ReasoningTree.tsx — 推理步骤树形展示
// ============================================================
import React from 'react';
import { Timeline, Tag, Card, Typography } from 'antd';
import { CheckCircleOutlined, FormOutlined, BulbOutlined } from '@ant-design/icons';
import type { ReasoningStep } from '../types';
import LatexRenderer from './LatexRenderer';

const { Text } = Typography;

interface ReasoningTreeProps {
  steps: ReasoningStep[];
}

const ReasoningTree: React.FC<ReasoningTreeProps> = ({ steps }) => (
  <Timeline
    items={steps.map((step, idx) => ({
      dot: <CheckCircleOutlined style={{ fontSize: 16, color: '#4f8cff' }} />,
      children: (
        <Card
          size="small"
          key={step.step_id || idx}
          style={{
            background: '#111827',
            borderColor: '#1e2d4a',
            marginBottom: 8,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Tag color="blue" style={{ margin: 0 }}>Step {step.step_id || idx + 1}</Tag>
            {step.method && (
              <Tag icon={<BulbOutlined />} color="purple" style={{ margin: 0 }}>
                {step.method}
              </Tag>
            )}
          </div>
          <Text style={{ color: '#c0d0e8', lineHeight: 1.8 }}>
            <LatexRenderer content={step.description} />
          </Text>
          {step.formula && (
            <div
              style={{
                marginTop: 10,
                padding: '10px 16px',
                background: '#0a0e17',
                borderRadius: 6,
                border: '1px solid #1e2d4a',
                overflowX: 'auto',
              }}
            >
              <FormOutlined style={{ color: '#4f8cff', marginRight: 8 }} />
              <LatexRenderer content={`$$${step.formula}$$`} />
            </div>
          )}
          {step.result && (
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>结果: </Text>
              <LatexRenderer content={step.result} />
            </div>
          )}
        </Card>
      ),
    }))}
  />
);

export default ReasoningTree;
