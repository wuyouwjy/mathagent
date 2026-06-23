// ============================================================
// router/index.tsx — 路由配置
// ============================================================
import { createBrowserRouter } from 'react-router-dom';
import MainLayout from '../layouts/MainLayout';
import Dashboard from '../pages/Dashboard';
import ProblemLibrary from '../pages/ProblemLibrary';
import AgentCenter from '../pages/AgentCenter';
import TaskRecords from '../pages/TaskRecords';
import ResultAnalysis from '../pages/ResultAnalysis';
import BenchmarkCenter from '../pages/BenchmarkCenter';
import SystemConfig from '../pages/SystemConfig';
import LogCenter from '../pages/LogCenter';
import About from '../pages/About';

const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'problems', element: <ProblemLibrary /> },
      { path: 'agent', element: <AgentCenter /> },
      { path: 'tasks', element: <TaskRecords /> },
      { path: 'analysis', element: <ResultAnalysis /> },
      { path: 'benchmark', element: <BenchmarkCenter /> },
      { path: 'config', element: <SystemConfig /> },
      { path: 'logs', element: <LogCenter /> },
      { path: 'about', element: <About /> },
    ],
  },
]);

export default router;
