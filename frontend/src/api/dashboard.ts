import client from './client';
import type { DashboardStats } from '../types';

export async function fetchDashboardStats(): Promise<DashboardStats> {
  return client.get('/dashboard') as Promise<DashboardStats>;
}
