// ============================================================
// pages/About.tsx — 关于系统
// ============================================================
import React, { useEffect, useState } from 'react';
import { Card, Typography, Descriptions, Tag, Row, Col, Spin, Divider } from 'antd';
import { ExperimentOutlined, GithubOutlined, ApiOutlined } from '@ant-design/icons';
import { fetchDashboardStats } from '../api/dashboard';
import type { DashboardStats } from '../types';

const { Title, Text, Paragraph } = Typography;

const About: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardStats().then(setStats).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Title level={4} style={{ color: '#e0e6f0', margin: 0, marginBottom: 16 }}>
        ❓ 关于系统
      </Title>

      <Row gutter={16}>
        <Col span={16}>
          <Card style={{ background: '#111827', borderColor: '#1e2d4a', marginBottom: 16 }}>
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <ExperimentOutlined style={{ fontSize: 64, color: '#4f8cff', marginBottom: 16 }} />
              <Title level={2} style={{ color: '#e0e6f0', margin: 0 }}>
                Math-Agent-System
              </Title>
              <Text style={{ color: '#8899b4', fontSize: 16 }}>
                基于 LangGraph + Intern-S1 API 的多领域数学自动求解智能体系统
              </Text>
            </div>

            <Divider style={{ borderColor: '#1e2d4a' }} />

            <Paragraph style={{ color: '#c0d0e8', fontSize: 14, lineHeight: 2.2 }}>
              Math-Agent-System 是一个面向科研场景的 AI 数学推理平台。
              系统采用多 Agent 协作架构，支持 18 个数学领域的自动求解，
              覆盖偏微分方程、常微分方程、复分析、拓扑学、运筹学、概率论、代数学、几何学、数论等多个领域。
            </Paragraph>

            <Title level={5} style={{ color: '#4f8cff', marginTop: 24 }}>
              <ApiOutlined /> 系统架构
            </Title>
            <Paragraph style={{ color: '#c0d0e8', lineHeight: 2.2 }}>
              1. <Tag color="blue">Problem Parser</Tag> — 问题解析器：将自然语言问题结构化
              <br />
              2. <Tag color="purple">Classifier Agent</Tag> — 分类器：识别问题所属数学领域
              <br />
              3. <Tag color="cyan">RAG Retrieval</Tag> — 知识检索：从定理库/公式库检索相关知识
              <br />
              4. <Tag color="green">Solver Agents</Tag> — 求解器：6个专业Solver，覆盖18个领域
              <br />
              5. <Tag color="orange">Verifier Agent</Tag> — 验证器：多策略验证求解结果
              <br />
              6. <Tag color="red">Reflection Agent</Tag> — 反思器：分析失败原因，自动重试
              <br />
              7. <Tag color="magenta">JSON Formatter</Tag> — 格式化器：输出标准 JSON 结果
            </Paragraph>
          </Card>
        </Col>

        <Col span={8}>
          <Card title="系统信息" style={{ background: '#111827', borderColor: '#1e2d4a', marginBottom: 16 }}>
            {loading ? <Spin /> : (
              <Descriptions column={1} size="small" bordered>
                <Descriptions.Item label="版本">1.0.0</Descriptions.Item>
                <Descriptions.Item label="当前模型">{stats?.current_model || '-'}</Descriptions.Item>
                <Descriptions.Item label="API调用次数">{stats?.api_calls_today || 0}</Descriptions.Item>
                <Descriptions.Item label="Token使用量">{stats?.tokens_used_today || 0}</Descriptions.Item>
                <Descriptions.Item label="问题总数">{stats?.total_problems || 0}</Descriptions.Item>
                <Descriptions.Item label="成功求解">{stats?.solved_count || 0}</Descriptions.Item>
              </Descriptions>
            )}
          </Card>

          <Card title="技术栈" style={{ background: '#111827', borderColor: '#1e2d4a' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <Tag color="blue">Python 3.10+</Tag>
              <Tag color="purple">LangGraph</Tag>
              <Tag color="cyan">Intern-S1 API</Tag>
              <Tag color="green">SymPy</Tag>
              <Tag color="orange">FastAPI</Tag>
              <Tag color="magenta">React 18</Tag>
              <Tag color="blue">TypeScript</Tag>
              <Tag color="purple">Ant Design 5</Tag>
              <Tag color="cyan">ECharts 5</Tag>
              <Tag color="green">Vite 6</Tag>
              <Tag color="orange">LangChain</Tag>
              <Tag color="magenta">ChromaDB</Tag>
              <Tag color="blue">Pydantic</Tag>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default About;
