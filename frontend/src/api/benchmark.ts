import client from './client';
import type { BenchmarkStatus, BenchmarkResult, BenchmarkRunSummary, BenchmarkRunRecord } from '../types';

export async function fetchBenchmarkStatus(): Promise<BenchmarkStatus> {
  return client.get('/benchmark/status') as Promise<BenchmarkStatus>;
}
export async function startBenchmark(data: { dataset_path?: string; max_retries?: number; enable_rag?: boolean; use_answer_db?: boolean; max_reflection_count?: number; use_llm_verify?: boolean }): Promise<{ message: string; run_id: string }> {
  return client.post('/benchmark/start', data) as Promise<{ message: string; run_id: string }>;
}
export async function stopBenchmark(): Promise<{ message: string }> {
  return client.post('/benchmark/stop') as Promise<{ message: string }>;
}
export async function clearAnswerDb(): Promise<{ message: string; cleared_exact: number; cleared_vector: number }> {
  return client.post('/benchmark/clear-db') as Promise<{ message: string; cleared_exact: number; cleared_vector: number }>;
}
export async function getBenchmarkResults(): Promise<BenchmarkResult> {
  return client.get('/benchmark/results') as Promise<BenchmarkResult>;
}
export async function fetchDatasets(): Promise<{ datasets: { name: string; path: string; count: number }[] }> {
  return client.get('/benchmark/datasets') as Promise<{ datasets: { name: string; path: string; count: number }[] }>;
}

// 历史记录
export async function fetchBenchmarkRuns(): Promise<BenchmarkRunSummary[]> {
  return client.get('/benchmark/runs') as Promise<BenchmarkRunSummary[]>;
}
export async function fetchBenchmarkRun(runId: string): Promise<BenchmarkRunRecord> {
  return client.get(`/benchmark/runs/${runId}`) as Promise<BenchmarkRunRecord>;
}
export async function deleteBenchmarkRun(runId: string): Promise<{ message: string }> {
  return client.delete(`/benchmark/runs/${runId}`) as Promise<{ message: string }>;
}
