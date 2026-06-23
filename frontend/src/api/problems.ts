// ============================================================
// api/problems.ts — 问题库 API
// ============================================================
import client from './client';
import type { ProblemListResponse, Problem, MathDomain } from '../types';

export interface ProblemQuery {
  page?: number;
  page_size?: number;
  keyword?: string;
  domain?: string;
  status?: string;
  difficulty?: string;
}

export async function fetchProblems(params: ProblemQuery): Promise<ProblemListResponse> {
  return client.get('/problems', { params }) as Promise<ProblemListResponse>;
}

export async function fetchProblem(id: string): Promise<Problem> {
  return client.get(`/problems/${id}`) as Promise<Problem>;
}

export async function createProblem(data: {
  question_text: string;
  domain?: string;
  difficulty?: string;
  tags?: string[];
}): Promise<Problem> {
  return client.post('/problems', data) as Promise<Problem>;
}

export async function updateProblem(
  id: string,
  data: Record<string, unknown>
): Promise<Problem> {
  return client.put(`/problems/${id}`, data) as Promise<Problem>;
}

export async function deleteProblem(id: string): Promise<void> {
  return client.delete(`/problems/${id}`);
}

export async function importProblems(file: File): Promise<{ message: string; count: number }> {
  const formData = new FormData();
  formData.append('file', file);
  return client.post('/problems/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as Promise<{ message: string; count: number }>;
}

export async function fetchDomains(): Promise<{ domains: MathDomain[] }> {
  return client.get('/problems/domains/list') as Promise<{ domains: MathDomain[] }>;
}
