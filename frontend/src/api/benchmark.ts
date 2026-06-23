import client from './client';
import type { BenchmarkStatus, BenchmarkResult } from '../types';

export async function fetchBenchmarkStatus(): Promise<BenchmarkStatus> {
  return client.get('/benchmark/status') as Promise<BenchmarkStatus>;
}
export async function startBenchmark(data: { dataset_path?: string; max_retries?: number; enable_rag?: boolean }): Promise<{ message: string }> {
  return client.post('/benchmark/start', data) as Promise<{ message: string }>;
}
export async function stopBenchmark(): Promise<{ message: string }> {
  return client.post('/benchmark/stop') as Promise<{ message: string }>;
}
export async function getBenchmarkResults(): Promise<BenchmarkResult> {
  return client.get('/benchmark/results') as Promise<BenchmarkResult>;
}
