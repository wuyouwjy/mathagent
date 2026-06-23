// ============================================================
// api/solve.ts — 求解 API
// ============================================================
import client from './client';
import type { SolveResult } from '../types';

export interface SolveRequest {
  question: string;
  question_id?: string;
  max_retries?: number;
  enable_rag?: boolean;
}

export async function solveQuestion(data: SolveRequest): Promise<SolveResult> {
  return client.post('/solve', data) as Promise<SolveResult>;
}

export async function solveFromFile(file: File): Promise<SolveResult> {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/solve/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  }) as Promise<SolveResult>;
}

export async function batchSolve(questions: SolveRequest[]): Promise<{
  task_id: string;
  total: number;
  solved: number;
  failed: number;
  results: SolveResult[];
}> {
  return client.post('/solve/batch', { questions, parallel: false }) as Promise<{
    task_id: string;
    total: number;
    solved: number;
    failed: number;
    results: SolveResult[];
  }>;
}
