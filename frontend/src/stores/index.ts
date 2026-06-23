// ============================================================
// stores/index.ts — 全局 Zustand 状态管理
// ============================================================
import { create } from 'zustand';

interface AppState {
  // 侧边栏折叠
  collapsed: boolean;
  toggleCollapsed: () => void;

  // 当前求解结果
  lastSolveResult: Record<string, unknown> | null;
  setSolveResult: (result: Record<string, unknown> | null) => void;

  // 求解中
  solving: boolean;
  setSolving: (v: boolean) => void;

  // 当前高亮节点 (Agent运行中心流程图)
  activeNode: string | null;
  setActiveNode: (node: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  collapsed: false,
  toggleCollapsed: () => set((s) => ({ collapsed: !s.collapsed })),

  lastSolveResult: null,
  setSolveResult: (result) => set({ lastSolveResult: result }),

  solving: false,
  setSolving: (v) => set({ solving: v }),

  activeNode: null,
  setActiveNode: (node) => set({ activeNode: node }),
}));
