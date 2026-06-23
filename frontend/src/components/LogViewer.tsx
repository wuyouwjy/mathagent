// ============================================================
// components/LogViewer.tsx — 实时日志窗口
// ============================================================
import React, { useRef, useEffect } from 'react';
import { Typography, Tag } from 'antd';
import type { LogEntry } from '../types';

const { Text } = Typography;

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'default',
  INFO: 'blue',
  WARNING: 'orange',
  ERROR: 'red',
  CRITICAL: 'magenta',
};

interface LogViewerProps {
  logs: LogEntry[];
  maxHeight?: number;
  autoScroll?: boolean;
}

const LogViewer: React.FC<LogViewerProps> = ({ logs, maxHeight = 400, autoScroll = true }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  return (
    <div
      ref={containerRef}
      style={{
        background: '#060b14',
        borderRadius: 8,
        border: '1px solid #1e2d4a',
        padding: 12,
        maxHeight,
        overflow: 'auto',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        fontSize: 12,
        lineHeight: 1.8,
      }}
    >
      {logs.length === 0 ? (
        <Text style={{ color: '#5a6d8a' }}>暂无日志</Text>
      ) : (
        logs.map((log, i) => (
          <div key={i} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {log.timestamp && (
              <Text style={{ color: '#5a6d8a', marginRight: 8 }}>{log.timestamp}</Text>
            )}
            <Tag color={LEVEL_COLORS[log.level] || 'default'} style={{ marginRight: 8, fontSize: 10 }}>
              {log.level}
            </Tag>
            {log.source && (
              <Text style={{ color: '#6366f1', marginRight: 8 }}>{log.source}</Text>
            )}
            <Text
              style={{
                color: log.level === 'ERROR' ? '#fca5a5' : log.level === 'WARNING' ? '#fde68a' : '#c0d0e8',
              }}
            >
              {log.message}
            </Text>
          </div>
        ))
      )}
    </div>
  );
};

export default LogViewer;
