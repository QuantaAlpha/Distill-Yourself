/**
 * Shared mutable state — import { state } from './state.js'
 * All modules read/write properties on this single object reference.
 */
export const state = {
  allSessions: [],
  allProjects: [],
  currentProject: null,
  currentSessionId: null,
  userOnlyMode: false,
  allCollapsed: false,
  currentDateFilter: "all",
  currentSourceFilter: "all",
  searchDebounceTimer: null,
  lastSearchResults: [],
  lastSearchQuery: "",
  _searchAbort: null,
  _sessionAbort: null,
  outlineVisible: true,
  _scrollHandler: null,
  _sidebarScrollHandler: null,
  _visibilityHandler: null,
  currentMessages: [],
  currentView: "sessions",
  viewHistory: [],
  currentSidebarPanel: "sessions",
  MAIN_VIEW_HASHES: new Set(["sessions", "insights", "ai", "twin"]),

  // Chat state — dual surface: session AI (right panel) + global AI (standalone view)
  globalChatHistory: [],
  currentGlobalChatId: null,
  sessionChatCache: {},
  sessionAiLoading: false,
  globalAiLoading: false,
  sessionAiHandle: null,
  globalAiHandle: null,

  // Global AI scope state
  globalScopeSource: localStorage.getItem("chatview-ai-scope-source") || "all",
  globalScopeDate: localStorage.getItem("chatview-ai-scope-date") || "7d",
  globalScopeProject: localStorage.getItem("chatview-ai-scope-project") || "",
  globalScopeEngine: localStorage.getItem("chatview-engine") || "auto",
  availableEngines: [],
  chatTimeout: parseInt(localStorage.getItem("chatview-timeout") || "900", 10),

  // Insights page state
  insightsActiveTab: "heatmap",
  insightsDataCache: { analytics: null, health: null, snippets: null },
};
