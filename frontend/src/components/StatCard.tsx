// ============================================================
// components/StatCard.tsx — 统计卡片
// ============================================================
import React from 'react';
import { Card, Statistic, Tooltip } from 'antd';
import { CaretUpOutlined, CaretDownOutlined } from '@ant-design/icons';

interface StatCardProps {
  title: string;
  value: number | string;
  suffix?: string;
  prefix?: React.ReactNode;
  icon?: React.ReactNode;
  color?: string;
  trend?: 'up' | 'down';
  trendValue?: string;
  loading?: boolean;
  onClick?: () => void;
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  suffix,
  prefix,
  icon,
  color = '#4f8cff',
  trend,
  trendValue,
  loading,
  onClick,
}) => (
  <Card
    hoverable={!!onClick}
    onClick={onClick}
    loading={loading}
    style={{
      background: 'linear-gradient(135deg, #111827 0%, #1a2236 100%)',
      borderColor: '#1e2d4a',
      borderRadius: 12,
      cursor: onClick ? 'pointer' : 'default',
    }}
    bodyStyle={{ padding: '20px 24px' }}
  >
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <div style={{ color: '#8899b4', fontSize: 13, marginBottom: 8, fontWeight: 500 }}>
          {title}
        </div>
        <Statistic
          value={value}
          suffix={suffix ? <span style={{ fontSize: 14, color: '#5a6d8a' }}>{suffix}</span> : undefined}
          prefix={prefix}
          valueStyle={{ color, fontSize: 28, fontWeight: 700, fontFamily: 'monospace' }}
          loading={loading}
        />
        {trend && trendValue && (
          <div style={{ marginTop: 4, fontSize: 12 }}>
            {trend === 'up' ? (
              <CaretUpOutlined style={{ color: '#52c41a' }} />
            ) : (
              <CaretDownOutlined style={{ color: '#ff4d4f' }} />
            )}
            <span style={{ color: trend === 'up' ? '#52c41a' : '#ff4d4f', marginLeft: 4 }}>
              {trendValue}
            </span>
          </div>
        )}
      </div>
      {icon && (
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            background: `${color}15`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 24,
            color,
          }}
        >
          {icon}
        </div>
      )}
    </div>
  </Card>
);

export default StatCard;
