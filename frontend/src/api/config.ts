import client from './client';
import type { SystemConfig } from '../types';

export async function fetchConfig(): Promise<SystemConfig> {
  return client.get('/config') as Promise<SystemConfig>;
}
export async function updateConfig(data: Partial<SystemConfig>): Promise<{ message: string; updated_fields: string[] }> {
  return client.put('/config', data) as Promise<{ message: string; updated_fields: string[] }>;
}
export async function resetConfig(): Promise<{ message: string }> {
  return client.post('/config/reset') as Promise<{ message: string }>;
}
