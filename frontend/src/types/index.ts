// ============================================================
// types/index.ts — 全局类型定义
// ============================================================

// 求解结果
export interface ReasoningStep {
  step_id: number;
  description: string;
  formula?: string;
  result?: string;
  method?: string;
}

export interface VerificationResult {
  is_correct: boolean;
  confidence: number;
  check_method?: string;
  error_details?: string;
}

export interface SolveResult {
  question_id: string;
  domain: string;
  final_answer: string;
  reasoning_steps: ReasoningStep[];
  methods_used: string[];
  verification: VerificationResult;
  educational_hint: string;
  computation_time_ms: number;
  retry_count: number;
  model_version?: string;
  node_trace: string[];
}

// 问题
export interface Problem {
  id: string;
  question_text: string;
  domain: string;
  difficulty: string;
  status: 'pending' | 'solved' | 'failed';
  created_at: string;
  updated_at?: string;
  tags?: string[];
  final_answer?: string;
  reasoning_steps?: ReasoningStep[];
  methods_used?: string[];
  verification?: VerificationResult;
  educational_hint?: string;
  computation_time_ms?: number;
  raw_output?: SolveResult;
}

export interface ProblemListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Problem[];
}

// 任务
export interface TaskItem {
  task_id: string;
  question_count: number;
  status: 'running' | 'completed' | 'failed';
  solved_count: number;
  failed_count: number;
  avg_confidence: number;
  total_time_ms: number;
  model_name: string;
  created_at: string;
  completed_at?: string;
}

export interface TaskListResponse {
  total: number;
  items: TaskItem[];
}

export interface TaskDetail extends TaskItem {
  results: SolveResult[];
  logs: string[];
}

// Dashboard
export interface DashboardStats {
  total_problems: number;
  solved_count: number;
  failed_count: number;
  avg_time_ms: number;
  avg_accuracy: number;
  current_model: string;
  api_calls_today: number;
  tokens_used_today: number;
}

// Benchmark
export interface BenchmarkStatus {
  running: boolean;
  progress: number;
  total: number;
  solved: number;
  failed: number;
  elapsed_seconds: number;
  estimated_remaining_seconds?: number;
  domain_accuracy: Record<string, number>;
  current_question?: string;
}

export interface BenchmarkResult {
  total: number;
  solved: number;
  failed: number;
  accuracy: number;
  avg_confidence: number;
  total_time_ms: number;
  avg_time_per_question_ms: number;
  domain_accuracy: Record<string, number>;
  results: SolveResult[];
}

// 系统配置
export interface SystemConfig {
  api_base_url: string;
  api_key: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
  max_reflection_count: number;
  enable_rag: boolean;
  solver_timeout: number;
  top_p: number;
}

// 日志
export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  source?: string;
}

export interface LogsResponse {
  total_lines: number;
  lines: LogEntry[];
}

// 领域
export interface MathDomain {
  domain_key: string;
  domain_cn: string;
  solver: string;
}

// API 通用响应
export interface ApiResponse<T> {
  data: T;
  message?: string;
  code?: number;
}
