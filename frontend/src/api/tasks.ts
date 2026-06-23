import client from './client';
import type { TaskListResponse, TaskDetail } from '../types';

export async function fetchTasks(params: { page?: number; page_size?: number }): Promise<TaskListResponse> {
  return client.get('/tasks', { params }) as Promise<TaskListResponse>;
}
export async function fetchTask(id: string): Promise<TaskDetail> {
  return client.get(`/tasks/${id}`) as Promise<TaskDetail>;
}
