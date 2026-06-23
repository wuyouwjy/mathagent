// ============================================================
// components/JsonViewer.tsx — JSON 可视化展示
// ============================================================
import React from 'react';
import { JsonView, defaultStyles } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';

interface JsonViewerProps {
  data: Record<string, unknown>;
}

const JsonViewer: React.FC<JsonViewerProps> = ({ data }) => (
  <div
    style={{
      background: '#0a0e17',
      borderRadius: 8,
      padding: 16,
      border: '1px solid #1e2d4a',
      maxHeight: 500,
      overflow: 'auto',
      fontSize: 13,
    }}
  >
    <JsonView
      data={data}
      style={{
        ...defaultStyles,
        container: { ...defaultStyles.container, backgroundColor: 'transparent' },
        stringValue: { ...defaultStyles.stringValue, color: '#6ee7b7' },
        numberValue: { ...defaultStyles.numberValue, color: '#93c5fd' },
        booleanValue: { ...defaultStyles.booleanValue, color: '#c084fc' },
        nullValue: { ...defaultStyles.nullValue, color: '#f87171' },
        label: { ...defaultStyles.label, color: '#f59e0b' },
        punctuation: { ...defaultStyles.punctuation, color: '#5a6d8a' },
      }}
    />
  </div>
);

export default JsonViewer;
