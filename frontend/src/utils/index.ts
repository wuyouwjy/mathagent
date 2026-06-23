// ============================================================
// utils/index.ts — 工具函数
// ============================================================

/** 毫秒格式化 */
export function formatMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}min`;
}

/** 时间格式化 */
export function formatTime(isoStr: string): string {
  if (!isoStr) return '-';
  return isoStr.replace('T', ' ').substring(0, 19);
}

/** 截断文本 */
export function truncate(text: string, maxLen: number = 100): string {
  if (!text) return '';
  return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}

/** 获取状态标签颜色 */
export function getStatusColor(status: string): string {
  const map: Record<string, string> = {
    pending: 'default',
    solved: 'success',
    failed: 'error',
    running: 'processing',
    completed: 'success',
  };
  return map[status] || 'default';
}

/** 获取领域中文名 */
export function getDomainCn(key: string): string {
  const map: Record<string, string> = {
    partial_differential_equations: '偏微分方程',
    ordinary_differential_equations: '常微分方程',
    complex_analysis: '复分析',
    real_analysis: '实分析',
    functional_analysis: '泛函分析',
    calculus_of_variations: '变分法',
    algebra: '代数',
    number_theory: '数论',
    group_theory: '群论',
    topology: '拓扑学',
    differential_geometry: '微分几何',
    algebraic_geometry: '代数几何',
    optimization: '运筹学/最优化',
    probability: '概率论',
    statistics: '统计学',
    numerical_analysis: '数值分析',
    combinatorics: '组合数学',
    mathematical_physics: '数学物理',
  };
  return map[key] || key;
}

/** 获取难度颜色 */
export function getDifficultyColor(d: string): string {
  const map: Record<string, string> = {
    easy: 'green',
    medium: 'orange',
    hard: 'red',
  };
  return map[d] || 'default';
}
