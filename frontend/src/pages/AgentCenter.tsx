// ============================================================
// pages/AgentCenter.tsx — Agent 运行中心 (核心页面)
// 布局: 左输入 | 中流程图 | 右状态
// ============================================================
import React, { useState } from 'react';
import {
  Row, Col, Card, Input, Button, Space, Tag, Typography, Divider, Upload,
  Steps, Statistic, message, Spin,
} from 'antd';
import {
  ThunderboltOutlined, SendOutlined, StopOutlined, ReloadOutlined,
  UploadOutlined, ClockCircleOutlined, ApiOutlined, CodeOutlined,
} from '@ant-design/icons';
import WorkflowGraph from '../components/WorkflowGraph';
import ReasoningTree from '../components/ReasoningTree';
import JsonViewer from '../components/JsonViewer';
import LatexRenderer from '../components/LatexRenderer';
import { solveQuestion, solveFromFile } from '../api/solve';
import type { SolveResult } from '../types';
import { useAppStore } from '../stores';
import { formatMs } from '../utils';

const { TextArea } = Input;
const { Title, Text } = Typography;

const DEFAULT_QUESTION = `求解二次方程 x^2 - 5x + 6 = 0`;

const AgentCenter: React.FC = () => {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [solving, setSolving] = useState(false);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const handleSolve = async () => {
    if (!question.trim()) {
      message.warning('请输入数学问题');
      return;
    }
    setSolving(true);
    setResult(null);
    setActiveNode('problem_parser');
    const startTime = Date.now();

    const nodeSequence = [
      'problem_parser', 'classifier', 'rag_retrieval',
      'solver_dispatcher', 'verifier', 'reflection', 'formatter',
    ];
    let nodeIdx = 0;
    const nodeInterval = setInterval(() => {
      if (nodeIdx < nodeSequence.length) {
        setActiveNode(nodeSequence[nodeIdx]);
        nodeIdx++;
      }
    }, 800);

    try {
      const res = await solveQuestion({ question: question.trim(), max_retries: 3, enable_rag: true });
      setResult(res);
      setActiveNode(null);
      setElapsed(Date.now() - startTime);
      message.success('求解完成!');
    } catch (e) {
      message.error('求解失败');
      setActiveNode(null);
    } finally {
      clearInterval(nodeInterval);
      setSolving(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setSolving(true);
    setResult(null);
    try {
      const res = await solveFromFile(file);
      setResult(res);
      message.success('求解完成!');
    } catch (e) {
      message.error('求解失败');
    } finally {
      setSolving(false);
    }
    return false;
  };

  const handleStop = () => {
    setSolving(false);
    message.info('求解已停止');
  };

  const verification = result?.verification;

  return (
    <div>
      <Title level={4} style={{ color: '#e0e6f0', margin: 0, marginBottom: 20 }}>
        <ThunderboltOutlined style={{ marginRight: 8, color: '#f59e0b' }} />
        Agent 运行中心
      </Title>

      <Row gutter={[16, 16]}>
        {/* 左侧：输入区 */}
        <Col xs={24} lg={7}>
          <Card
            title="📝 问题输入"
            style={{ background: '#111827', borderColor: '#1e2d4a', height: '100%' }}
            styles={{ body: { padding: 16 } }}
          >
            <TextArea
              rows={8}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="请输入数学问题，支持 LaTeX 格式..."
              style={{ marginBottom: 12 }}
            />
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space>
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSolve}
                  loading={solving}
                  size="large"
                >
                  运行求解
                </Button>
                <Button icon={<StopOutlined />} onClick={handleStop} disabled={!solving}>
                  停止
                </Button>
                <Button icon={<ReloadOutlined />} onClick={() => { setResult(null); setQuestion(''); }}>
                  清空
                </Button>
              </Space>
              <Upload accept=".txt,.json" showUploadList={false} beforeUpload={handleFileUpload}>
                <Button icon={<UploadOutlined />} block>
                  上传文件 (.txt / .json)
                </Button>
              </Upload>
            </Space>

            <Divider />

            {/* 运行状态摘要 */}
            <div style={{ color: '#8899b4', fontSize: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span><ClockCircleOutlined /> 耗时</span>
                <Text style={{ color: '#c0d0e8' }}>{result ? formatMs(result.computation_time_ms) : '-'}</Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span><ApiOutlined /> Token</span>
                <Text style={{ color: '#c0d0e8' }}>-</Text>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span><CodeOutlined /> 模型</span>
                <Tag color="purple" style={{ margin: 0 }}>{result?.model_version || 'intern-latest'}</Tag>
              </div>
            </div>
          </Card>
        </Col>

        {/* 中间：流程图 */}
        <Col xs={24} lg={10}>
          <Card
            title="🧬 LangGraph 工作流"
            style={{ background: '#111827', borderColor: '#1e2d4a' }}
            styles={{ body: { padding: 8 } }}
          >
            {solving && (
              <div style={{ textAlign: 'center', marginBottom: 8 }}>
                <Spin size="small" />
                <Text style={{ color: '#8899b4', marginLeft: 8, fontSize: 12 }}>
                  当前节点: <Tag color="blue">{activeNode}</Tag>
                </Text>
              </div>
            )}
            <WorkflowGraph activeNode={activeNode} height={380} />
          </Card>

          {/* 最终答案 */}
          {result && (
            <Card
              title="✅ 求解结果"
              style={{ marginTop: 16, background: '#111827', borderColor: '#1e2d4a' }}
            >
              <div style={{ marginBottom: 12 }}>
                <Statistic
                  title="最终答案"
                  value={result.final_answer?.substring(0, 100)}
                  valueStyle={{ color: '#10b981', fontSize: 20, fontWeight: 600 }}
                />
              </div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                <Tag color="blue">{result.domain}</Tag>
                {verification && (
                  <Tag color={verification.is_correct ? 'green' : 'red'}>
                    {verification.is_correct ? '✅ 验证通过' : '❌ 验证未通过'} ({verification.confidence?.toFixed(2)})
                  </Tag>
                )}
                <Tag>{result.retry_count}次重试</Tag>
              </div>
              <LatexRenderer content={result.educational_hint} />
            </Card>
          )}
        </Col>

        {/* 右侧：状态与日志 */}
        <Col xs={24} lg={7}>
          <Card
            title="📊 运行详情"
            style={{ background: '#111827', borderColor: '#1e2d4a', marginBottom: 16 }}
          >
            {!result ? (
              <Text style={{ color: '#5a6d8a' }}>等待求解...</Text>
            ) : (
              <div>
                <Steps
                  direction="vertical"
                  size="small"
                  current={result.node_trace?.length || 0}
                  items={(result.node_trace || []).map((t) => ({
                    title: <Text style={{ fontSize: 12, color: '#c0d0e8' }}>{t}</Text>,
                    status: 'finish' as const,
                  }))}
                />
                <Divider />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text style={{ color: '#8899b4', fontSize: 12 }}>使用的方法</Text>
                </div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {result.methods_used?.map((m, i) => (
                    <Tag key={i} color="purple">{m}</Tag>
                  )) || <Tag>无</Tag>}
                </div>
              </div>
            )}
          </Card>

          {result?.reasoning_steps && result.reasoning_steps.length > 0 && (
            <Card
              title="🧠 推理步骤"
              style={{ background: '#111827', borderColor: '#1e2d4a' }}
            >
              <ReasoningTree steps={result.reasoning_steps} />
            </Card>
          )}
        </Col>
      </Row>

      {/* 底部 JSON 结果 */}
      {result && (
        <Card
          title="📄 完整 JSON 输出"
          style={{ marginTop: 16, background: '#111827', borderColor: '#1e2d4a' }}
        >
          <JsonViewer data={result as unknown as Record<string, unknown>} />
        </Card>
      )}
    </div>
  );
};

export default AgentCenter;
