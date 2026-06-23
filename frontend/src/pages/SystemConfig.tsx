// ============================================================
// pages/SystemConfig.tsx — 系统配置页面
// ============================================================
import React, { useEffect, useState } from 'react';
import { Card, Form, Input, InputNumber, Switch, Button, Typography, message, Spin, Divider } from 'antd';
import { SaveOutlined, UndoOutlined } from '@ant-design/icons';
import { fetchConfig, updateConfig, resetConfig } from '../api/config';
import type { SystemConfig } from '../types';

const { Title } = Typography;

const SystemConfigPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const config = await fetchConfig();
      form.setFieldsValue(config);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const values = await form.validateFields();
      const res = await updateConfig(values);
      message.success(`配置已更新: ${res.updated_fields.join(', ')}`);
    } catch (e) {
      console.error(e);
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    await resetConfig();
    message.success('配置已重置');
    await loadConfig();
  };

  return (
    <div>
      <Title level={4} style={{ color: '#e0e6f0', margin: 0, marginBottom: 16 }}>
        ⚙️ 系统配置
      </Title>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
      ) : (
        <Card style={{ background: '#111827', borderColor: '#1e2d4a', maxWidth: 800 }}>
          <Form form={form} layout="vertical">
            <Title level={5} style={{ color: '#4f8cff' }}>🔑 API 配置</Title>
            <Form.Item name="api_base_url" label="API 基础地址">
              <Input placeholder="https://chat.intern-ai.org.cn/api/v1/" />
            </Form.Item>
            <Form.Item name="api_key" label="API Key">
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Form.Item name="model_name" label="模型名称">
              <Input placeholder="intern-latest" />
            </Form.Item>

            <Divider style={{ borderColor: '#1e2d4a' }} />

            <Title level={5} style={{ color: '#4f8cff' }}>🎛️ 模型参数</Title>
            <Form.Item name="temperature" label="Temperature (温度)">
              <InputNumber min={0} max={2} step={0.05} style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="max_tokens" label="Max Tokens (最大Token数)">
              <InputNumber min={100} max={65536} step={100} style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="top_p" label="Top P">
              <InputNumber min={0} max={1} step={0.01} style={{ width: 200 }} />
            </Form.Item>

            <Divider style={{ borderColor: '#1e2d4a' }} />

            <Title level={5} style={{ color: '#4f8cff' }}>⚡ 工作流配置</Title>
            <Form.Item name="max_reflection_count" label="最大反思重试次数">
              <InputNumber min={0} max={10} style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="solver_timeout" label="Solver 超时 (秒)">
              <InputNumber min={10} max={3600} style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="enable_rag" label="启用 RAG 检索" valuePropName="checked">
              <Switch />
            </Form.Item>

            <Divider style={{ borderColor: '#1e2d4a' }} />

            <div style={{ display: 'flex', gap: 12 }}>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
                保存配置
              </Button>
              <Button icon={<UndoOutlined />} onClick={handleReset}>
                重置默认
              </Button>
            </div>
          </Form>
        </Card>
      )}
    </div>
  );
};

export default SystemConfigPage;
