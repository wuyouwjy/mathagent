// ============================================================
// pages/TaskRecords.tsx — 求解任务记录
// ============================================================
import React, { useEffect, useState } from 'react';
import { Table, Button, Tag, Typography, Drawer, Descriptions, Divider, Collapse } from 'antd';
import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { fetchTasks, fetchTask } from '../api/tasks';
import type { TaskItem, TaskDetail } from '../types';
import { formatMs, getStatusColor } from '../utils';
import ReasoningTree from '../components/ReasoningTree';
import JsonViewer from '../components/JsonViewer';
import LogViewer from '../components/LogViewer';

const { Title, Text } = Typography;

const TaskRecords: React.FC = () => {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 详情抽屉
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [taskDetail, setTaskDetail] = useState<TaskDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const res = await fetchTasks({ page: 1, page_size: 50 });
      setTasks(res.items);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTasks(); }, []);

  const handleView = async (taskId: string) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    try {
      const detail = await fetchTask(taskId);
      setTaskDetail(detail);
    } finally {
      setDetailLoading(false);
    }
  };

  const columns: ColumnsType<TaskItem> = [
    { title: '任务ID', dataIndex: 'task_id', width: 140, ellipsis: true },
    { title: '问题数量', dataIndex: 'question_count', width: 90 },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (s: string) => <Tag color={getStatusColor(s)}>{s}</Tag>,
    },
    { title: '成功', dataIndex: 'solved_count', width: 70 },
    { title: '失败', dataIndex: 'failed_count', width: 70 },
    {
      title: '平均置信度', dataIndex: 'avg_confidence', width: 110,
      render: (v: number) => v?.toFixed(4),
    },
    {
      title: '总耗时', dataIndex: 'total_time_ms', width: 110,
      render: (v: number) => formatMs(v),
    },
    { title: '模型', dataIndex: 'model_name', width: 120, ellipsis: true },
    { title: '创建时间', dataIndex: 'created_at', width: 170 },
    {
      title: '操作', width: 80,
      render: (_, record) => (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleView(record.task_id)}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ color: '#e0e6f0', margin: 0 }}>📋 求解任务记录</Title>
        <Button icon={<ReloadOutlined />} onClick={loadTasks}>刷新</Button>
      </div>

      <Table
        columns={columns}
        dataSource={tasks}
        rowKey="task_id"
        loading={loading}
        size="middle"
        pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条任务` }}
      />

      {/* 任务详情抽屉 */}
      <Drawer
        title="任务详情"
        placement="right"
        width={700}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setTaskDetail(null); }}
        styles={{ header: { background: '#0d1321', borderBottom: '1px solid #1e2d4a' }, body: { background: '#0a0e17', padding: 24 } }}
        loading={detailLoading}
      >
        {taskDetail && (
          <div style={{ color: '#e0e6f0' }}>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="任务ID">{taskDetail.task_id}</Descriptions.Item>
              <Descriptions.Item label="状态"><Tag color={getStatusColor(taskDetail.status)}>{taskDetail.status}</Tag></Descriptions.Item>
              <Descriptions.Item label="问题总数">{taskDetail.question_count}</Descriptions.Item>
              <Descriptions.Item label="成功/失败">{taskDetail.solved_count}/{taskDetail.failed_count}</Descriptions.Item>
              <Descriptions.Item label="平均置信度">{taskDetail.avg_confidence?.toFixed(4)}</Descriptions.Item>
              <Descriptions.Item label="总耗时">{formatMs(taskDetail.total_time_ms)}</Descriptions.Item>
              <Descriptions.Item label="模型">{taskDetail.model_name}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{taskDetail.created_at}</Descriptions.Item>
            </Descriptions>

            <Divider />

            <Title level={5} style={{ color: '#c0d0e8' }}>📊 每题结果</Title>
            {taskDetail.results?.map((r, i) => (
              <Collapse
                key={r.question_id || i}
                ghost
                items={[{
                  key: r.question_id || i,
                  label: (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Tag color="blue">{i + 1}</Tag>
                      <Text style={{ color: '#c0d0e8' }}>{r.question_id}</Text>
                      <Tag color={r.verification?.is_correct ? 'green' : 'red'}>
                        {r.verification?.is_correct ? '✅' : '❌'}
                      </Tag>
                      <Text style={{ color: '#5a6d8a' }}>{r.domain}</Text>
                    </div>
                  ),
                  children: (
                    <div>
                      <Text strong style={{ color: '#4f8cff' }}>答案: </Text>
                      <Text style={{ color: '#e0e6f0' }}>{r.final_answer}</Text>
                      {r.reasoning_steps?.length > 0 && (
                        <>
                          <Divider style={{ margin: '12px 0' }} />
                          <ReasoningTree steps={r.reasoning_steps} />
                        </>
                      )}
                      <Divider style={{ margin: '12px 0' }} />
                      <Collapse ghost items={[{
                        key: 'json',
                        label: <Text style={{ color: '#4f8cff' }}>📄 JSON</Text>,
                        children: <JsonViewer data={r as unknown as Record<string, unknown>} />,
                      }]} />
                    </div>
                  ),
                }]}
              />
            ))}

            {taskDetail.logs?.length > 0 && (
              <>
                <Divider />
                <Title level={5} style={{ color: '#c0d0e8' }}>📑 日志</Title>
                <LogViewer
                  logs={taskDetail.logs.map((l, i) => ({
                    timestamp: '', level: 'INFO', message: l,
                  }))}
                />
              </>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default TaskRecords;
