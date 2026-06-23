import client from './client';
import type { LogsResponse } from '../types';

export async function fetchLogs(params: { lines?: number; level?: string; keyword?: string }): Promise<LogsResponse> {
  return client.get('/logs', { params }) as Promise<LogsResponse>;
}
export async function clearLogs(): Promise<void> {
  return client.delete('/logs');
}
export function getLogDownloadUrl(): string {
  return '/api/logs/download';
}
