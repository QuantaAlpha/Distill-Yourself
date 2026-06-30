/**
 * ES Module entry point — wires all modules together and boots the app.
 *
 * Replaces the original IIFE in static/app.js.
 */

import { state } from "./state.js";
import { $, $$, dom, initDom } from "./dom.js";
import {
  api,
  initThemeToggle,
  esc,
  renderMarkdownSimple,
  readSseStream,
  autoResizeTextarea,
} from "./utils.js";
import {
  renderSessions,
  renderProjects,
  updateWelcomeStats,
  registerSessionDeps,
} from "./sessions.js";
import {
  loadSession,
  applyUserOnlyFilter,
  registerConversationDeps,
  renderMessages,
} from "./conversation.js";
import { doSearch, renderSearchResults, jumpToMessage } from "./search.js";
import {
  handleKeyboard,
  buildOutline,
  highlightOutlineItem,
} from "./keyboard.js";
import { openInsights, bindInsightsTabs, loadInsightsTab } from "./insights.js";
import {
  initAiPage,
  notifyEvolveScopeChanged,
  renderAiScopeBar,
  loadChatFromStorage,
  newGlobalChat,
  submitGlobalAi,
  _stopGlobalAi,
  populateGlobalAiPresets,
} from "./evolve-page.js";
import {
  exportMarkdown,
  copyConversation,
  exportJson,
  exportTwinData,
} from "./export.js";
import {
  openSessionAiPanel,
  updateSessionAiHeader,
  restoreSessionAiMessages,
  submitSessionAi,
  _stopSessionAi,
} from "./session-ai.js";
import { loadSessionSummary } from "./session-summary.js";
import { setLang, applyLang, getLang, t } from "./lang.js";

// ── Wire cross-module dependencies ─────────────────────────────
registerSessionDeps({
  showView,
  switchSidebarPanel,
  loadSession,
});

registerConversationDeps({
  showView,
  buildOutline,
  highlightOutlineItem,
  jumpToMessage,
  updateSessionAiHeader,
  restoreSessionAiMessages,
});

// ── Expose globals for evolve.js / twin.js (non-module scripts) ─
window.esc = esc;
window.renderMarkdownSimple = renderMarkdownSimple;
window.readSseStream = readSseStream;
Object.defineProperty(window, "allSessions", { get: () => state.allSessions });

// ── View Switching ─────────────────────────────────────────────
export function showView(name, pushHistory = true) {
  if (pushHistory && state.currentView !== name) {
    state.viewHistory.push(state.currentView);
    if (state.viewHistory.length > 50)
      state.viewHistory = state.viewHistory.slice(-20);
  }
  // Clean up conversation scroll handler when leaving conversation view
  if (state.currentView === "conversation" && name !== "conversation") {
    const mc = document.getElementById("messages-container");
    if (mc && state._scrollHandler) {
      mc.removeEventListener("scroll", state._scrollHandler);
      state._scrollHandler = null;
    }
  }
  // Clean up sidebar scroll handler when leaving sessions view
  if (state.currentView === "sessions" && name !== "sessions") {
    const sidebarContent = document.getElementById("sidebar-content");
    if (sidebarContent && state._sidebarScrollHandler) {
      sidebarContent.removeEventListener("scroll", state._sidebarScrollHandler);
      state._sidebarScrollHandler = null;
    }
  }
  state.currentView = name;
  if (
    pushHistory &&
    state.MAIN_VIEW_HASHES.has(name) &&
    window.location.hash !== `#${name}`
  ) {
    history.pushState({ view: name }, "", `#${name}`);
  }
  const twinView = $("#twin-view");
  const views = {
    conversation: dom.convView,
    search: dom.searchResults,
    insights: dom.insightsView,
    ai: dom.aiView,
    twin: twinView,
  };
  for (const [k, el] of Object.entries(views)) {
    if (el) el.classList.toggle("hidden", k !== name);
  }
  const emptyState = $("#empty-state");
  if (emptyState) emptyState.classList.toggle("hidden", name !== "sessions");
  // Sidebar panel: sessions list by default, chat history for AI page
  if (name === "ai") {
    switchSidebarPanel("chat");
  } else {
    switchSidebarPanel("sessions");
  }
  // Initialize Twin view when switching to it
  if (name === "twin" && window.initTwinView) window.initTwinView();
  // Update sidebar nav active state
  const navView =
    name === "conversation" || name === "search" ? "sessions" : name;
  document
    .querySelectorAll(".sidebar-nav-item")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === navView));
}

function goBack() {
  const prev = state.viewHistory.pop() || "sessions";
  showView(prev, false);
  if (state.MAIN_VIEW_HASHES.has(prev)) {
    history.replaceState({ view: prev }, "", `#${prev}`);
  }
}

function restoreViewFromHash() {
  const hash = window.location.hash.slice(1);
  if (!state.MAIN_VIEW_HASHES.has(hash)) return false;
  restoreMainView(hash, false);
  history.replaceState({ view: hash }, "", `#${hash}`);
  return true;
}

function restoreMainView(view, pushHistory = false) {
  state.currentSessionId = null;
  if (view === "insights") {
    openInsights(pushHistory);
  } else if (view === "ai") {
    showView("ai", pushHistory);
    initAiPage();
  } else {
    showView(view, pushHistory);
  }
}

function restoreSessionFromHash() {
  const hash = window.location.hash.slice(1);
  if (!hash || state.MAIN_VIEW_HASHES.has(hash)) return false;
  const match = state.allSessions.find((s) => s.id === hash);
  if (match && match.source) {
    state.currentSourceFilter = match.source;
    renderSessions(state.allSessions);
  }
  history.replaceState(
    { view: "conversation", sessionId: hash },
    "",
    `#${hash}`,
  );
  loadSession(hash, undefined, false);
  return true;
}

export function switchSidebarPanel(panel) {
  state.currentSidebarPanel = panel;
  document.querySelectorAll(".sidebar-panel").forEach((p) => {
    p.classList.toggle("hidden", !p.id.endsWith(panel));
  });
}

// ── Onboarding ────────────────────────────────────────────────
// Shows guided setup steps when 0 sessions exist
function toggleOnboarding(sessions) {
  const onboarding = document.getElementById("onboarding-steps");
  if (!onboarding) return;
  const show = sessions && sessions.length === 0;
  onboarding.classList.toggle("hidden", !show);
  if (show) {
    const btn = document.getElementById("onboarding-index-btn");
    if (btn) {
      btn.onclick = async () => {
        btn.disabled = true;
        btn.textContent = "⏳ Indexing...";
        try {
          await api("/api/refresh");
          const [projects, sessionsFA] = await Promise.all([
            api("/api/projects"),
            api("/api/sessions"),
          ]);
          state.allSessions = sessionsFA;
          state.allProjects = projects;
          renderProjects(projects);
          renderSessions(sessionsFA);
          dom.searchStats.textContent = `${sessionsFA.length} sessions`;
          updateWelcomeStats(sessionsFA, projects);
          toggleOnboarding(sessionsFA);
          if (window.showToast) window.showToast.success("Indexing complete!");
        } catch (e) {
          if (window.showToast)
            window.showToast.error("Indexing failed: " + e.message, 0, {
              label: "Retry",
              callback: () => btn.click(),
            });
          btn.disabled = false;
          btn.textContent = "🔄 Retry";
        }
      };
    }
  }
}

// ── Browser Notification Permission Check ────────────────────
function initNotifications() {
  if (!("Notification" in window)) return;
  if (Notification.permission === "default") {
    // Defer request until user interacts — request on first meaningful action
    const reqOnce = () => {
      Notification.requestPermission();
      document.removeEventListener("click", reqOnce);
    };
    document.addEventListener("click", reqOnce, { once: true });
  }
}

// Helper to send a browser notification
function sendBrowserNotification(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    try {
      new Notification(title, { body, icon: "/favicon.ico" });
    } catch (e) {
      /* Notification API may not be available in all contexts */
    }
  }
}
window.sendBrowserNotification = sendBrowserNotification;

// ── Welcome Card Actions ────────────────────────────────────────
function openInsightsTab(tabName) {
  showView("insights");
  bindInsightsTabs();
  state.insightsActiveTab = tabName;
  document
    .querySelectorAll(".insights-tab")
    .forEach((t) => t.classList.toggle("active", t.dataset.tab === tabName));
  loadInsightsTab(tabName);
}

function bindWelcomeCards() {
  document.querySelectorAll(".welcome-card").forEach((card) => {
    card.addEventListener("click", () => {
      const action = card.dataset.action;
      if (action === "sessions" || action === "ai" || action === "twin") {
        document
          .querySelector(`.sidebar-nav-item[data-view="${action}"]`)
          ?.click();
      } else if (
        action === "heatmap" ||
        action === "hotspots" ||
        action === "errors" ||
        action === "health" ||
        action === "snippets"
      ) {
        openInsightsTab(action);
      } else if (action === "profile") {
        document.querySelector('.sidebar-nav-item[data-view="ai"]')?.click();
      }
    });
  });
}

// Render welcome hint with kbd tags and i18n params
function renderWelcomeHint() {
  const hint = $("#welcome-hint");
  if (!hint) return;
  const keys = ["/", "j", "k", "?"];
  // 不传位置参数：t() 会把 {0}/{1} 直接替换成字面字符，导致下面 split 占位符失效。
  // 这里保留原始 {0}~{3} 占位符，再自行 split 注入 <kbd> 标签。
  const parts = t("welcome.hint").split(/(\{\d+\})/g);
  hint.innerHTML = parts
    .map((part) => {
      const m = part.match(/^\{(\d+)\}$/);
      if (m) return `<kbd>${keys[parseInt(m[1])] || ""}</kbd>`;
      return esc(part);
    })
    .join("");
}

function formatEngineLabel(engine) {
  return engine === "auto"
    ? "Auto"
    : engine.charAt(0).toUpperCase() + engine.slice(1);
}

function ensureEngineOption(select, engine) {
  if (!select || !engine) return;
  if ([...select.options].some((opt) => opt.value === engine)) return;
  const opt = document.createElement("option");
  opt.value = engine;
  opt.textContent = formatEngineLabel(engine);
  select.appendChild(opt);
}

// ── Event Bindings ─────────────────────────────────────────────
function bindEvents() {
  // Filter button + popover
  const filterBtn = $("#filter-btn");
  const filterPopover = $("#filter-popover");
  if (filterBtn && filterPopover) {
    filterBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = !filterPopover.classList.contains("hidden");
      filterPopover.classList.toggle("hidden", open);
      filterBtn.classList.toggle("active", !open);
    });
    // Close popover on outside click
    document.addEventListener("click", (e) => {
      if (!filterPopover.contains(e.target) && e.target !== filterBtn) {
        filterPopover.classList.add("hidden");
        filterBtn.classList.remove("active");
      }
    });
  }

  // Filter clear button
  const filterClear = $("#filter-clear");
  if (filterClear) {
    filterClear.addEventListener("click", (e) => {
      e.stopPropagation();
      state.currentSourceFilter = "all";
      state.currentDateFilter = "all";
      state.currentProject = null;
      const textEl = $("#project-trigger-text");
      if (textEl) textEl.textContent = t("sessions.allProjects");
      renderSessions(state.allSessions);
    });
  }

  // Global engine selector (header)
  const globalEngineSelect = $("#global-engine-select");
  if (globalEngineSelect) {
    ensureEngineOption(globalEngineSelect, "auto");
    ensureEngineOption(globalEngineSelect, state.globalScopeEngine);
    globalEngineSelect.value = state.globalScopeEngine;
    globalEngineSelect.addEventListener("change", () => {
      state.globalScopeEngine = globalEngineSelect.value;
      // 持久化引擎选择，刷新后保持
      localStorage.setItem("chatview-engine", state.globalScopeEngine);
      localStorage.setItem(
        "chatview-ai-scope-source",
        state.globalScopeSource || "all",
      );
      localStorage.setItem(
        "chatview-ai-scope-date",
        state.globalScopeDate || "7d",
      );
      localStorage.setItem(
        "chatview-ai-scope-project",
        state.globalScopeProject || "",
      );
      // Sync with AI page scope bar selector if it exists
      const scopeEngine = $("#ai-scope-engine");
      if (scopeEngine) scopeEngine.value = state.globalScopeEngine;
      if (typeof notifyEvolveScopeChanged === "function")
        notifyEvolveScopeChanged();
    });
  }

  // Language toggle (pill switch)
  const langToggle = $("#lang-toggle");
  if (langToggle) {
    const currentLang = getLang();
    langToggle.dataset.active = currentLang;
    langToggle.querySelectorAll(".lang-opt").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.lang === currentLang);
      btn.addEventListener("click", () => {
        const lang = btn.dataset.lang;
        if (lang === getLang()) return;
        setLang(lang);
        langToggle.dataset.active = lang;
        langToggle
          .querySelectorAll(".lang-opt")
          .forEach((b) =>
            b.classList.toggle("active", b.dataset.lang === lang),
          );
        // Re-render presets (they use t() at render time)
        const presetContainer = $("#ai-chat-presets");
        if (presetContainer) {
          presetContainer.removeAttribute("data-populated");
          populateGlobalAiPresets();
        }
        // Re-render welcome stats (pass both sessions and projects)
        const projects = state.allSessions
          ? [
              ...new Set(
                state.allSessions.map((s) => s.project).filter(Boolean),
              ),
            ]
          : [];
        updateWelcomeStats(state.allSessions, projects);
        // Re-render welcome hint (kbd tags + params)
        renderWelcomeHint();
      });
    });
  }

  // Apply saved language on load
  applyLang();
  // Render welcome hint with kbd tags on initial load
  renderWelcomeHint();

  // Global search
  dom.searchInput.addEventListener("input", () => {
    clearTimeout(state.searchDebounceTimer);
    state.searchDebounceTimer = setTimeout(
      () => doSearch(dom.searchInput.value.trim()),
      300,
    );
  });
  dom.searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      dom.searchInput.value = "";
      showView("sessions");
    }
  });
  dom.searchSortSelect.addEventListener("change", () => {
    if (state.lastSearchResults.length) renderSearchResults();
  });

  // Keyboard shortcuts (F5)
  document.addEventListener("keydown", handleKeyboard);

  // Logo -> sessions
  const logo = $("#logo");
  if (logo)
    logo.addEventListener("click", (e) => {
      e.preventDefault();
      showView("sessions");
    });

  // Top nav items
  document.querySelectorAll(".sidebar-nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      const view = btn.dataset.view;
      // Highlight active nav
      document
        .querySelectorAll(".sidebar-nav-item")
        .forEach((b) => b.classList.toggle("active", b === btn));
      // Show the right main view
      if (view === "sessions") {
        showView("sessions");
      } else if (view === "insights") {
        openInsights();
      } else if (view === "ai") {
        showView("ai");
        initAiPage();
      } else if (view === "twin") {
        showView("twin");
      }
    });
  });

  // Project dropdown toggle
  dom.projectTrigger.addEventListener("click", () => {
    dom.projectDropdown.classList.toggle("hidden");
  });
  // Close dropdown on outside click
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#project-bar")) {
      dom.projectDropdown.classList.add("hidden");
    }
  });

  // Back button -> previous view
  $("#btn-back").addEventListener("click", goBack);

  // Refresh current session
  $("#btn-refresh").addEventListener("click", async () => {
    if (state.currentSessionId) {
      await api("/api/refresh");
      loadSession(state.currentSessionId);
    }
  });

  // User-only toggle
  $("#btn-user-only").addEventListener("click", function () {
    state.userOnlyMode = !state.userOnlyMode;
    this.classList.toggle("active", state.userOnlyMode);
    applyUserOnlyFilter();
  });

  // Collapse/Expand all toggle — tool bodies start collapsed (display:none)
  // So first click should EXPAND all, not collapse
  $("#btn-collapse-all").addEventListener("click", function () {
    state.allCollapsed = !state.allCollapsed;
    // allCollapsed=true means "show expanded" (since initial is collapsed)
    this.textContent = state.allCollapsed
      ? t("conv.collapseAll")
      : t("conv.expandAll");
    this.classList.toggle("active", state.allCollapsed);
    $$(".tool-body, .thinking-body").forEach((el) => {
      el.style.display = state.allCollapsed ? "" : "none";
    });
    $$(".tool-toggle").forEach((el) => {
      el.classList.toggle("open", state.allCollapsed);
    });
    // Also handle tool call groups
    $$(".tool-group-body").forEach((el) => {
      el.style.display = state.allCollapsed ? "" : "none";
    });
    $$(".tool-group-toggle").forEach((el) => {
      el.classList.toggle("open", state.allCollapsed);
    });
    $$(".tool-call-group").forEach((el) => {
      el.classList.toggle("collapsed", !state.allCollapsed);
    });
    // Assistant turn bars (process blocks live inside .turn-body)
    $$(".turn-body").forEach((el) => {
      el.style.display = state.allCollapsed ? "" : "none";
    });
    $$(".turn-collapse-bar").forEach((el) => {
      el.classList.toggle("collapsed", !state.allCollapsed);
    });
    $$(".turn-collapse-toggle").forEach((el) => {
      el.classList.toggle("open", state.allCollapsed);
    });
    // Long assistant replies + collapsible user text
    const foldLabel = state.allCollapsed
      ? t("conv.collapse")
      : t("conv.showMore");
    $$(".reply-card").forEach((el) => {
      el.classList.toggle("collapsed", !state.allCollapsed);
    });
    $$(".text-collapsible").forEach((el) => {
      el.classList.toggle("collapsed", !state.allCollapsed);
    });
    $$(".reply-fold, .reply-text-toggle, .msg-fold, .text-toggle").forEach(
      (el) => {
        el.textContent = foldLabel;
      },
    );
  });

  // Right panel tab switching
  document.querySelectorAll(".rp-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const panel = tab.dataset.panel;
      document
        .querySelectorAll(".rp-tab")
        .forEach((t) => t.classList.toggle("active", t === tab));
      document
        .querySelectorAll(".rp-content")
        .forEach((c) => c.classList.toggle("hidden", !c.id.endsWith(panel)));
      // Lazy-load summary when switching to that tab
      if (panel === "summary" && state.currentSessionId) {
        loadSessionSummary(state.currentSessionId);
      }
    });
  });

  // Export (F4)
  $("#btn-export").addEventListener("click", exportMarkdown);

  // Export JSON
  $("#btn-export-json").addEventListener("click", exportJson);

  // Copy conversation (User + Assistant text only)
  $("#btn-copy-conv").addEventListener("click", copyConversation);

  // ── Session AI bindings (right panel) ──
  const sessionAiSend = $("#session-ai-send");
  const sessionAiInput = $("#session-ai-input");
  if (sessionAiSend)
    sessionAiSend.addEventListener("click", () => {
      if (state.sessionAiLoading && state.sessionAiHandle) {
        _stopSessionAi();
      } else {
        submitSessionAi();
      }
    });
  if (sessionAiInput) {
    sessionAiInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        if (state.sessionAiLoading && state.sessionAiHandle) {
          _stopSessionAi();
        } else {
          submitSessionAi();
        }
      }
    });
    sessionAiInput.addEventListener("input", () =>
      autoResizeTextarea(sessionAiInput),
    );
  }
  // Session AI presets (inside #session-ai-presets)
  document
    .querySelectorAll("#session-ai-presets .preset-card")
    .forEach((btn) => {
      btn.addEventListener("click", () => submitSessionAi(btn.dataset.prompt));
    });

  // ── Global AI bindings (AI page chat panel) ──
  const chatSendBtn = $("#ai-chat-send");
  const chatInput = $("#ai-chat-input");
  if (chatSendBtn)
    chatSendBtn.addEventListener("click", () => {
      if (state.globalAiLoading && state.globalAiHandle) {
        _stopGlobalAi();
      } else {
        submitGlobalAi();
      }
    });
  if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        if (state.globalAiLoading && state.globalAiHandle) {
          _stopGlobalAi();
        } else {
          submitGlobalAi();
        }
      }
    });
    chatInput.addEventListener("input", () => autoResizeTextarea(chatInput));
  }

  // Global AI presets (populated dynamically)
  const btnNewChatAi = $("#btn-new-chat-ai");
  if (btnNewChatAi) btnNewChatAi.addEventListener("click", newGlobalChat);
  const btnNewChatSidebar = $("#btn-new-chat");
  if (btnNewChatSidebar)
    btnNewChatSidebar.addEventListener("click", newGlobalChat);

  // Load persisted chat history
  loadChatFromStorage();

  // Browser back/forward button support
  window.addEventListener("popstate", (e) => {
    const st = e.state;
    if (st && st.view === "conversation" && st.sessionId) {
      loadSession(st.sessionId, undefined, false);
    } else if (st && state.MAIN_VIEW_HASHES.has(st.view)) {
      restoreMainView(st.view, false);
    } else {
      restoreViewFromHash() ||
        restoreSessionFromHash() ||
        showView("sessions", false);
      state.currentSessionId = null;
    }
  });

  // Sidebar toggle — mobile drawer (.open) + desktop collapse (.collapsed)
  const sidebarToggle = $("#sidebar-toggle");
  const sidebarEl = dom.sidebar;
  const sidebarOverlay = $("#sidebar-overlay");
  if (sidebarToggle && sidebarEl) {
    // Restore desktop collapsed state
    if (
      window.innerWidth > 768 &&
      localStorage.getItem("sidebar-collapsed") === "1"
    ) {
      sidebarEl.classList.add("collapsed");
    }
    const closeSidebar = () => sidebarEl.classList.remove("open");
    sidebarToggle.addEventListener("click", () => {
      if (window.innerWidth <= 768) {
        sidebarEl.classList.toggle("open");
      } else {
        const collapsed = sidebarEl.classList.toggle("collapsed");
        localStorage.setItem("sidebar-collapsed", collapsed ? "1" : "0");
      }
    });
    if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);
    // Close sidebar when a session is selected on mobile
    dom.sessionList.addEventListener("click", (e) => {
      if (e.target.closest("li") && window.innerWidth <= 768) closeSidebar();
    });
  }
}

// ── Adaptive session polling ──────────────────────────────────
let _lastKnownGen = 0;
let _pollTimer = null;
const POLL_INTERVAL_ACTIVE = 30000; // 30s when tab visible
const POLL_INTERVAL_HIDDEN = 120000; // 2min when tab hidden

function startSessionPolling() {
  schedulePoll();
  // Remove any previous listener to prevent leaks
  if (state._visibilityHandler) {
    document.removeEventListener("visibilitychange", state._visibilityHandler);
  }
  state._visibilityHandler = () => {
    clearTimeout(_pollTimer);
    if (!document.hidden) pollOnce();
    schedulePoll();
  };
  document.addEventListener("visibilitychange", state._visibilityHandler);
}

function schedulePoll() {
  clearTimeout(_pollTimer);
  const interval = document.hidden
    ? POLL_INTERVAL_HIDDEN
    : POLL_INTERVAL_ACTIVE;
  _pollTimer = setTimeout(async () => {
    await pollOnce();
    schedulePoll();
  }, interval);
}

async function pollOnce() {
  try {
    const check = await api("/api/sessions/check");
    if (check.gen !== _lastKnownGen && _lastKnownGen !== 0) {
      // Generation changed -- refresh session list
      const [projects, sessions] = await Promise.all([
        api("/api/projects"),
        api("/api/sessions"),
      ]);
      state.allSessions = sessions;
      state.allProjects = projects;
      renderProjects(projects);
      renderSessions(sessions);
      dom.searchStats.textContent = `${sessions.length} sessions`;
      updateWelcomeStats(sessions, projects);
      state.insightsDataCache = {
        analytics: null,
        health: null,
        snippets: null,
      };
      if (state.currentView === "search" && dom.searchInput.value.trim()) {
        doSearch(dom.searchInput.value.trim());
      }
    }
    _lastKnownGen = check.gen;
  } catch (e) {
    /* silent */
  }
}

// ── Engine detection ───────────────────────────────────────────
async function detectEngines() {
  try {
    const prevEngine = state.globalScopeEngine;
    const data = await api("/api/engines");
    state.availableEngines = data.engines || [];
    // Update header engine selector with available engines + "auto" option
    const sel = $("#global-engine-select");
    if (sel) {
      const engineOptions = Array.from(
        new Set(["auto", ...state.availableEngines]),
      );
      sel.innerHTML = "";
      for (const eng of engineOptions) {
        const opt = document.createElement("option");
        opt.value = eng;
        opt.textContent = formatEngineLabel(eng);
        sel.appendChild(opt);
      }
      // Restore user's saved selection, or default to "auto"
      const saved = localStorage.getItem("chatview-engine");
      if (saved && engineOptions.includes(saved)) {
        state.globalScopeEngine = saved;
      } else if (
        !state.globalScopeEngine ||
        !engineOptions.includes(state.globalScopeEngine)
      ) {
        state.globalScopeEngine = "auto";
      }
      sel.value = state.globalScopeEngine;
      sel.disabled = engineOptions.length <= 1;
    }
    if (document.getElementById("ai-scope-bar")) {
      renderAiScopeBar();
      if (
        state.currentView === "ai" &&
        prevEngine !== state.globalScopeEngine
      ) {
        notifyEvolveScopeChanged();
      }
    }
  } catch (e) {
    /* silent -- keep current value */
  }
}

// ── Resizable panels (drag handles) ────────────────────────────
function initResizeHandles() {
  document.querySelectorAll(".resize-handle[data-target]").forEach((handle) => {
    const targetId = handle.dataset.target;
    const storageKey = `chatview-panel-width-${targetId}`;

    // Restore saved width
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      const target = document.getElementById(targetId);
      if (target) target.style.width = saved + "px";
    }

    handle.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      handle.setPointerCapture(e.pointerId);
      handle.classList.add("active");
      document.body.classList.add("resizing");

      const target = document.getElementById(targetId);
      if (!target) return;
      const container = target.parentElement;
      const minW = parseInt(getComputedStyle(target).minWidth) || 220;
      const maxW = container.clientWidth * 0.5;

      function onMove(ev) {
        // Panel is on the right side, so width = container right - pointer X
        const containerRect = container.getBoundingClientRect();
        let newWidth = containerRect.right - ev.clientX;
        newWidth = Math.max(minW, Math.min(maxW, newWidth));
        target.style.width = newWidth + "px";
      }

      function onUp() {
        handle.classList.remove("active");
        document.body.classList.remove("resizing");
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
        // Persist
        localStorage.setItem(storageKey, parseInt(target.style.width));
      }

      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup", onUp);
    });
  });

  // Collapse / expand toggle buttons for right-side panels
  document.querySelectorAll(".panel-toggle[data-toggle]").forEach((btn) => {
    const targetId = btn.dataset.toggle;
    const collapseKey = `chatview-panel-collapsed-${targetId}`;
    const target = document.getElementById(targetId);
    if (!target) return;
    const sync = () => {
      const collapsed = target.classList.contains("panel-collapsed");
      btn.textContent = collapsed ? "\u2039" : "\u203a";
    };
    // Restore saved collapsed state
    if (localStorage.getItem(collapseKey) === "1") {
      target.classList.add("panel-collapsed");
    }
    sync();
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const collapsed = target.classList.toggle("panel-collapsed");
      localStorage.setItem(collapseKey, collapsed ? "1" : "0");
      sync();
    });
    // Prevent the resize drag from starting when pressing the toggle
    btn.addEventListener("pointerdown", (e) => e.stopPropagation());
  });
}

// ── Init ───────────────────────────────────────────────────────
async function init() {
  initThemeToggle();
  bindEvents();
  bindWelcomeCards();
  // Re-render JS-generated UI shell text when locale changes
  window.addEventListener("localechange", () => {
    applyLang(document);
    updateWelcomeStats(state.allSessions, state.allProjects || []);
    toggleOnboarding(state.allSessions);
    const presetContainer = $("#ai-chat-presets");
    if (presetContainer && presetContainer.dataset.populated)
      populateGlobalAiPresets();
    // Re-render the active conversation so JS-generated content text (turn headers,
    // fold buttons, labels) reflects the new locale.
    if (
      state.currentView === "conversation" &&
      state.currentMessages &&
      state.currentMessages.length
    ) {
      renderMessages(state.currentMessages);
    }
    // Re-render search results if they are currently displayed.
    if (state.lastSearchResults && state.lastSearchResults.length) {
      renderSearchResults();
    }
  });
  // Show loading state immediately
  dom.sessionList.innerHTML =
    '<li class="loading-placeholder"><div class="skeleton-line" style="width:70%"></div><div class="skeleton-line short"></div></li>'.repeat(
      8,
    );
  dom.searchStats.textContent = "Loading\u2026";

  // Load from cached index immediately (server builds index at startup)
  const [projects, sessions] = await Promise.all([
    api("/api/projects"),
    api("/api/sessions"),
  ]);
  state.allSessions = sessions;
  state.allProjects = projects;
  renderProjects(projects);
  renderSessions(sessions);
  dom.searchStats.textContent = `${sessions.length} sessions`;
  updateWelcomeStats(sessions, projects);
  toggleOnboarding(sessions);
  restoreViewFromHash() || restoreSessionFromHash();

  // Start adaptive session polling
  startSessionPolling();
  // Detect available AI engines in background
  detectEngines();
  // Init browser notifications
  initNotifications();
}

// ── Boot ───────────────────────────────────────────────────────
initDom();
initResizeHandles();
init().catch((err) => {
  console.error("Init failed:", err);
  const el = document.getElementById("content");
  if (el)
    el.innerHTML = `<div style="padding:60px 40px;text-align:center"><h2 style="color:var(--text)">Error</h2><p style="color:var(--text-muted)">${err.message}</p><p style="color:var(--text-muted)">Make sure server.py is running.</p></div>`;
});

// ── Re-exports for dynamic import() consumers (keyboard.js, insights.js) ──
export { loadSession, initAiPage, openSessionAiPanel };
