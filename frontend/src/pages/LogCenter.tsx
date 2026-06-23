// ============================================================
// pages/LogCenter.tsx — 日志中心
// ============================================================
import React, { useEffect, useState, useCallback } from 'react';
import { Card, Button, Select, Input, Space, Typography } from 'antd';
import { ReloadOutlined, DownloadOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import { fetchLogs, clearLogs, getLogDownloadUrl } from '../api/logs';
import type { LogEntry } from '../types';
import LogViewer from '../components/LogViewer';
import { usePolling } from '../hooks/usePolling';

const { Title } = Typography;

const LogCenter: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [level, setLevel] = useState<string>();
  const [keyword, setKeyword] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  const loadLogs = useCallback(async () => {
    try {
      const res = await fetchLogs({ lines: 500, level: level || undefined, keyword: keyword || undefined });
      setLogs(res.lines);
    } catch {}
  }, [level, keyword]);

  usePolling(loadLogs, 3000, autoRefresh);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  const handleDownload = () => {
    window.open(getLogDownloadUrl(), '_blank');
  };

  const handleClear = async () => {
    await clearLogs();
    setLogs([]);
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ color: '#e0e6f0', margin: 0 }}>📑 日志中心</Title>
        <Space>
          <Select
            placeholder="日志级别"
            value={level}
            onChange={setLevel}
            allowClear
            style={{ width: 120 }}
            options={[
              { label: 'DEBUG', value: 'DEBUG' },
              { label: 'INFO', value: 'INFO' },
              { label: 'WARNING', value: 'WARNING' },
              { label: 'ERROR', value: 'ERROR' },
            ]}
          />
          <Input
            placeholder="搜索日志..."
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <Button
            type={autoRefresh ? 'primary' : 'default'}
            onClick={() => setAutoRefresh(!autoRefresh)}
            size="small"
          >
            {autoRefresh ? '自动刷新中' : '自动刷新'}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={loadLogs}>刷新</Button>
          <Button icon={<DownloadOutlined />} onClick={handleDownload}>下载</Button>
          <Button icon={<DeleteOutlined />} onClick={handleClear} danger>清空</Button>
        </Space>
      </div>

      <Card style={{ background: '#111827', borderColor: '#1e2d4a' }}>
        <LogViewer logs={logs} maxHeight={600} autoScroll={autoRefresh} />
      </Card>
    </div>
  );
};

export default LogCenter;
