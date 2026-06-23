// ============================================================
// api/client.ts — Axios HTTP 客户端封装
// ============================================================
import axios from 'axios';
import { message } from 'antd';

const API_BASE = '/api';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 120000, // 120s timeout for solve requests
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
client.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg =
      error.response?.data?.detail ||
      error.message ||
      '网络请求失败';
    message.error(msg);
    return Promise.reject(error);
  }
);

export default client;
