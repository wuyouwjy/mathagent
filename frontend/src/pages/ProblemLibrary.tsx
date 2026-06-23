// ============================================================
// pages/ProblemLibrary.tsx — 数学问题库
// ============================================================
import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Input, Select, Tag, Space, Typography, Modal, Form,
  Upload, message,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, UploadOutlined, DeleteOutlined,
  EyeOutlined, ReloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import ProblemDrawer from '../components/ProblemDrawer';
import { fetchProblems, deleteProblem, importProblems, createProblem, fetchDomains } from '../api/problems';
import type { Problem } from '../types';
import { getDomainCn, getStatusColor, getDifficultyColor, truncate } from '../utils';

const { Title } = Typography;

const ProblemLibrary: React.FC = () => {
  const [data, setData] = useState<Problem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [filterDomain, setFilterDomain] = useState<string>();
  const [filterStatus, setFilterStatus] = useState<string>();
  const [domains, setDomains] = useState<{ domain_key: string; domain_cn: string }[]>([]);

  // 详情抽屉
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedProblem, setSelectedProblem] = useState<Problem | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);

  // 新增弹窗
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchProblems({
        page, page_size: 20, keyword: keyword || undefined,
        domain: filterDomain, status: filterStatus,
      });
      setData(res.items);
      setTotal(res.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, keyword, filterDomain, filterStatus]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => {
    fetchDomains().then((r) => setDomains(r.domains)).catch(() => {});
  }, []);

  const handleView = async (id: string) => {
    setDrawerOpen(true);
    setDrawerLoading(true);
    try {
      const { default: client } = await import('../api/client');
      const problem = await (await import('../api/problems')).fetchProblem(id);
      setSelectedProblem(problem);
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后不可恢复',
      okText: '删除',
      okType: 'danger',
      onOk: async () => {
        await deleteProblem(id);
        message.success('已删除');
        loadData();
      },
    });
  };

  const handleImport = async (file: File) => {
    const res = await importProblems(file);
    message.success(res.message);
    loadData();
    return false; // 阻止默认上传
  };

  const handleCreate = async () => {
    const values = await form.validateFields();
    await createProblem(values);
    message.success('创建成功');
    setModalOpen(false);
    form.resetFields();
    loadData();
  };

  const columns: ColumnsType<Problem> = [
    { title: 'ID', dataIndex: 'id', width: 100, ellipsis: true },
    {
      title: '问题内容', dataIndex: 'question_text', ellipsis: true,
      render: (t: string) => <span style={{ color: '#c0d0e8' }}>{truncate(t, 80)}</span>,
    },
    {
      title: '领域', dataIndex: 'domain', width: 130,
      render: (d: string) => d ? <Tag color="blue">{getDomainCn(d) || d}</Tag> : '-',
    },
    {
      title: '难度', dataIndex: 'difficulty', width: 80,
      render: (d: string) => <Tag color={getDifficultyColor(d)}>{d}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', width: 80,
      render: (s: string) => <Tag color={getStatusColor(s)}>{s}</Tag>,
    },
    { title: '创建时间', dataIndex: 'created_at', width: 170 },
    {
      title: '操作', width: 150,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleView(record.id)}>
            查看
          </Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)} />
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ color: '#e0e6f0', margin: 0 }}>📚 数学问题库</Title>
        <Space>
          <Upload accept=".json" showUploadList={false} beforeUpload={handleImport}>
            <Button icon={<UploadOutlined />}>导入 JSON</Button>
          </Upload>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新增问题
          </Button>
        </Space>
      </div>

      {/* 搜索栏 */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Input
          placeholder="搜索问题内容或ID"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="领域筛选"
          value={filterDomain}
          onChange={(v) => { setFilterDomain(v); setPage(1); }}
          allowClear
          style={{ width: 180 }}
          options={domains.map((d) => ({ label: d.domain_cn, value: d.domain_key }))}
        />
        <Select
          placeholder="状态筛选"
          value={filterStatus}
          onChange={(v) => { setFilterStatus(v); setPage(1); }}
          allowClear
          style={{ width: 130 }}
          options={[
            { label: '待求解', value: 'pending' },
            { label: '已求解', value: 'solved' },
            { label: '失败', value: 'failed' },
          ]}
        />
        <Button icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        size="middle"
        pagination={{
          current: page, total, pageSize: 20,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 题`,
          showSizeChanger: false,
        }}
      />

      {/* 详情抽屉 */}
      <ProblemDrawer
        open={drawerOpen}
        problem={selectedProblem}
        loading={drawerLoading}
        onClose={() => { setDrawerOpen(false); setSelectedProblem(null); }}
      />

      {/* 新增弹窗 */}
      <Modal
        title="新增问题"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="创建"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="question_text" label="问题文本" rules={[{ required: true, message: '请输入问题' }]}>
            <Input.TextArea rows={4} placeholder="请输入数学问题..." />
          </Form.Item>
          <Form.Item name="domain" label="数学领域">
            <Select
              options={domains.map((d) => ({ label: d.domain_cn, value: d.domain_key }))}
              placeholder="选择领域 (可选)"
            />
          </Form.Item>
          <Form.Item name="difficulty" label="难度" initialValue="medium">
            <Select options={[
              { label: '简单', value: 'easy' },
              { label: '中等', value: 'medium' },
              { label: '困难', value: 'hard' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ProblemLibrary;
