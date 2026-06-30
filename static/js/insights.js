/**
 * Insights page — analytics sub-renderers and tabbed UI.
 *
 * Usage:
 *   import { openInsights, bindInsightsTabs, loadInsightsTab, ... } from './insights.js';
 */

import { state } from './state.js';
import { esc, formatDate, api } from './utils.js';
import { t, registerI18n, applyLang } from './lang.js';

// ── i18n dictionary ──────────────────────────────────────────────
registerI18n({
  zh: {
    'insights.hotspots.title': '文件热点',
    'insights.hotspots.empty': '暂无文件热点数据。',
    'insights.hotspots.file': '文件',
    'insights.hotspots.edits': '编辑次数',
    'insights.hotspots.sessions': '会话数',
    'insights.hotspots.frequency': '频率',
    'insights.heatmap.title': '工具使用热力图',
    'insights.heatmap.subtitle': '（最近 30 天）',
    'insights.heatmap.empty': '暂无热力图数据。',
    'insights.errors.title': '错误模式',
    'insights.errors.empty': '未发现错误模式。',
    'insights.errors.occurrences': '次出现',
    'insights.errors.sessions': '次会话',
    'insights.health.title': '项目健康看板',
    'insights.health.project': '项目',
    'insights.health.source': '来源',
    'insights.health.sessions': '会话',
    'insights.health.messages': '消息',
    'insights.health.recent7d': '近 7 天',
    'insights.health.lastActive': '最后活跃',
    'insights.health.trend': '趋势',
    'insights.health.status': '状态',
    'insights.health.empty': '暂无项目数据。',
    'insights.health.staleDays': '{n} 天前',
    'insights.health.today': '今天',
    'insights.snippets.title': '代码片段',
    'insights.snippets.empty': '未找到代码片段。',
    'insights.snippets.searchPlaceholder': '搜索片段…',
    'insights.snippets.all': '全部 ({n})',
    'insights.snippets.applied': '✅ 已应用 ({n})',
    'insights.snippets.suggested': '建议 ({n})',
    'insights.snippets.appliedBadge': '✅ 已应用',
    'insights.snippets.suggestedBadge': '建议',
    'insights.snippets.copyCode': '复制代码',
    'insights.snippets.copied': '✓',
    'insights.snippets.code': '代码',
    'insights.loadFailed': '加载失败：{msg}',
    'insights.retry': '重试',
  },
  en: {
    'insights.hotspots.title': 'File Hotspots',
    'insights.hotspots.empty': 'No file hotspot data available.',
    'insights.hotspots.file': 'File',
    'insights.hotspots.edits': 'Edits',
    'insights.hotspots.sessions': 'Sessions',
    'insights.hotspots.frequency': 'Frequency',
    'insights.heatmap.title': 'Tool Usage Heatmap',
    'insights.heatmap.subtitle': '(last 30 days)',
    'insights.heatmap.empty': 'No heatmap data available.',
    'insights.errors.title': 'Error Patterns',
    'insights.errors.empty': 'No error patterns found.',
    'insights.errors.occurrences': 'occurrences',
    'insights.errors.sessions': 'sessions',
    'insights.health.title': 'Project Health Dashboard',
    'insights.health.project': 'Project',
    'insights.health.source': 'Source',
    'insights.health.sessions': 'Sessions',
    'insights.health.messages': 'Messages',
    'insights.health.recent7d': 'Recent (7d)',
    'insights.health.lastActive': 'Last Active',
    'insights.health.trend': 'Trend',
    'insights.health.status': 'Status',
    'insights.health.empty': 'No project data.',
    'insights.health.staleDays': '{n}d ago',
    'insights.health.today': 'today',
    'insights.snippets.title': 'Code Snippets',
    'insights.snippets.empty': 'No code snippets found.',
    'insights.snippets.searchPlaceholder': 'Search snippets…',
    'insights.snippets.all': 'All ({n})',
    'insights.snippets.applied': '✅ Applied ({n})',
    'insights.snippets.suggested': 'Suggested ({n})',
    'insights.snippets.appliedBadge': '✅ Applied',
    'insights.snippets.suggestedBadge': 'Suggested',
    'insights.snippets.copyCode': 'Copy code',
    'insights.snippets.copied': '✓',
    'insights.snippets.code': 'code',
    'insights.loadFailed': 'Failed: {msg}',
    'insights.retry': 'Retry',
  },
});

// ── Analytics sub-renderers (used by Insights tabs) ──────────
export function renderHotspotsSection(container, data) {
  if (!data.hotspots?.length) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:40px;text-align:center;color:var(--text-muted)";
    empty.textContent = t("insights.hotspots.empty");
    container.appendChild(empty);
    return;
  }
  const section = document.createElement("div");
  section.className = "analytics-section";
  const maxCount = data.hotspots[0].count;
  let html = `<h3><span class="a-icon">🔥</span> ${t("insights.hotspots.title")}</h3>`;
  html += `<table class="hotspot-table"><thead><tr><th>${t("insights.hotspots.file")}</th><th>${t("insights.hotspots.edits")}</th><th>${t("insights.hotspots.sessions")}</th><th>${t("insights.hotspots.frequency")}</th></tr></thead><tbody>`;
  data.hotspots.slice(0, 25).forEach(h => {
    const pct = maxCount > 0 ? (h.count / maxCount * 100) : 0;
    html += `<tr>
      <td><span class="hotspot-path" title="${esc(h.fullPath || h.path)}">${esc(h.path)}</span></td>
      <td>${h.count}</td>
      <td>${h.sessionCount}</td>
      <td><div class="hotspot-bar"><div class="hotspot-bar-fill" style="width:${pct}%"></div></div></td>
    </tr>`;
  });
  html += '</tbody></table>';
  section.innerHTML = html;
  container.appendChild(section);
}

export function renderHeatmapSection(container, data) {
  if (!data.heatmap?.days?.length || !data.heatmap?.tools?.length) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:40px;text-align:center;color:var(--text-muted)";
    empty.textContent = t("insights.heatmap.empty");
    container.appendChild(empty);
    return;
  }
  const section = document.createElement("div");
  section.className = "analytics-section";
  const hm = data.heatmap;
  let html = `<h3><span class="a-icon">🗓️</span> ${t("insights.heatmap.title")} <span style="font-size:11px;font-weight:400;color:var(--text-muted)">${t("insights.heatmap.subtitle")}</span></h3>`;
  let maxVal = 0;
  hm.days.forEach(day => { hm.tools.forEach(t => { maxVal = Math.max(maxVal, hm.data[day]?.[t] || 0); }); });

  html += `<div class="heatmap-grid" style="grid-template-columns: 80px repeat(${hm.days.length}, 1fr);">`;
  html += '<div></div>';
  hm.days.forEach(day => {
    html += `<div class="heatmap-day-label">${day.slice(5)}</div>`;
  });
  hm.tools.forEach(tool => {
    html += `<div class="heatmap-label">${esc(tool)}</div>`;
    hm.days.forEach(day => {
      const val = hm.data[day]?.[tool] || 0;
      const intensity = maxVal > 0 ? val / maxVal : 0;
      const bg = val > 0 ? `rgba(88,86,214,${0.1 + intensity * 0.8})` : 'var(--bg-surface2)';
      const color = intensity > 0.5 ? '#fff' : 'var(--text-muted)';
      html += `<div class="heatmap-cell" style="background:${bg};color:${color}" title="${tool}: ${val} calls on ${day}">${val || ''}</div>`;
    });
  });
  html += '</div>';

  html += '<div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">';
  hm.tools.forEach(tool => {
    const total = hm.totals[tool] || 0;
    html += `<span style="font-size:12px;padding:3px 8px;background:var(--bg-surface2);border-radius:12px;color:var(--text-secondary)"><strong>${esc(tool)}</strong> ${total}</span>`;
  });
  html += '</div>';

  section.innerHTML = html;
  container.appendChild(section);
}

export function renderErrorsSection(container, data) {
  if (!data.errors?.length) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:40px;text-align:center;color:var(--text-muted)";
    empty.textContent = t("insights.errors.empty");
    container.appendChild(empty);
    return;
  }
  const section = document.createElement("div");
  section.className = "analytics-section";
  let html = `<h3><span class="a-icon">⚠️</span> ${t("insights.errors.title")}</h3>`;
  html += '<ul class="error-list">';
  data.errors.forEach(e => {
    html += `<li class="error-item">
      <div class="error-pattern">${esc(e.pattern)}</div>
      <div class="error-meta">
        <span><strong>${e.count}</strong> ${t("insights.errors.occurrences")}</span>
        <span><strong>${e.sessionCount}</strong> ${t("insights.errors.sessions")}</span>
        <span>${e.firstSeen} → ${e.lastSeen}</span>
        <span>${e.projects.join(', ')}</span>
      </div>
    </li>`;
  });
  html += '</ul>';
  section.innerHTML = html;
  container.appendChild(section);
}

export function renderProjectHealthInto(container, data) {
  container.innerHTML = "";
  if (!data.projects?.length) {
    container.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t("insights.health.empty")}</div>`;
    return;
  }
  const sec = document.createElement("div");
  sec.className = "analytics-section";
  let html = `<h3><span class="a-icon">🏥</span> ${t("insights.health.title")}</h3>`;
  html += `<table class="health-table"><thead><tr>
    <th>${t("insights.health.project")}</th><th>${t("insights.health.source")}</th><th>${t("insights.health.sessions")}</th><th>${t("insights.health.messages")}</th><th>${t("insights.health.recent7d")}</th><th>${t("insights.health.lastActive")}</th><th>${t("insights.health.trend")}</th><th>${t("insights.health.status")}</th>
  </tr></thead><tbody>`;
  data.projects.forEach(p => {
    const trendIcon = p.trend === "up" ? "📈" : p.trend === "down" ? "📉" : "➡️";
    let staleClass = "fresh";
    let staleLabel;
    if (p.staleDays > 30) { staleClass = "stale"; staleLabel = `${p.staleDays}d`; }
    else if (p.staleDays > 7) { staleClass = "recent"; staleLabel = t("insights.health.staleDays", { n: p.staleDays }); }
    else if (p.staleDays <= 1) { staleLabel = t("insights.health.today"); }
    else { staleLabel = t("insights.health.staleDays", { n: p.staleDays }); }
    html += `<tr>
      <td><span class="health-name">${esc(p.name)}</span></td>
      <td><span class="source-badge ${p.source}">${esc(p.source)}</span></td>
      <td>${p.sessionCount}</td>
      <td>${p.totalMessages}</td>
      <td>${p.recentSessions}</td>
      <td>${esc(p.lastSeen)}</td>
      <td class="health-trend">${trendIcon}</td>
      <td><span class="health-stale ${staleClass}">${staleLabel}</span></td>
    </tr>`;
  });
  html += '</tbody></table>';
  sec.innerHTML = html;
  container.appendChild(sec);
}

export function renderSnippetsInto(container, data) {
  container.innerHTML = "";
  if (!data.snippets?.length) {
    container.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t("insights.snippets.empty")}</div>`;
    return;
  }
  const appliedCount = data.snippets.filter(s => s.applied).length;
  const toolbar = document.createElement("div");
  toolbar.style.cssText = "margin-bottom:16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  toolbar.innerHTML = `
    <input type="text" id="snippet-search" data-i18n-placeholder="insights.snippets.searchPlaceholder" style="flex:1;min-width:200px;padding:6px 12px;border:1px solid var(--border-light);border-radius:var(--radius-sm);font-size:13px;background:var(--bg-surface);outline:none">
    <button class="snippet-filter-btn active" data-filter="all">${t("insights.snippets.all", { n: data.snippets.length })}</button>
    <button class="snippet-filter-btn" data-filter="applied">${t("insights.snippets.applied", { n: appliedCount })}</button>
    <button class="snippet-filter-btn" data-filter="suggested">${t("insights.snippets.suggested", { n: data.snippets.length - appliedCount })}</button>`;
  container.appendChild(toolbar);

  const listDiv = document.createElement("div");
  listDiv.id = "snippet-list";
  container.appendChild(listDiv);

  let currentFilter = "all";
  function renderList(items) {
    listDiv.innerHTML = "";
    items.forEach(s => {
      const card = document.createElement("div");
      card.className = "snippet-card";
      const badge = s.applied
        ? `<span class="snippet-badge applied">${t("insights.snippets.appliedBadge")}</span>`
        : `<span class="snippet-badge suggested">${t("insights.snippets.suggestedBadge")}</span>`;
      card.innerHTML = `
        <div class="snippet-header">
          <span class="snippet-lang">${esc(s.language || t("insights.snippets.code"))}</span>
          ${badge}
          <span class="snippet-context">${esc(s.context)}</span>
          <span class="snippet-meta">${esc(s.project)} · ${formatDate(s.date)}</span>
        </div>
        <div class="snippet-code-wrap">
          <div class="snippet-code">${esc(s.code)}</div>
          <button class="snippet-copy" data-i18n-title="insights.snippets.copyCode">📋</button>
        </div>`;
      card.querySelector(".snippet-header").addEventListener("click", async () => {
        const { loadSession } = await import('./app.js');
        loadSession(s.sessionId);
      });
      card.querySelector(".snippet-copy").addEventListener("click", (e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(s.code).then(() => {
          const btn = card.querySelector(".snippet-copy");
          btn.textContent = "✓";
          setTimeout(() => { btn.textContent = "📋"; }, 1500);
        });
      });
      listDiv.appendChild(card);
    });
  }

  function applyFilters() {
    const q = (container.querySelector("#snippet-search")?.value || "").toLowerCase();
    let items = data.snippets;
    if (currentFilter === "applied") items = items.filter(s => s.applied);
    else if (currentFilter === "suggested") items = items.filter(s => !s.applied);
    if (q) items = items.filter(s =>
      (s.code || '').toLowerCase().includes(q) || (s.context || '').toLowerCase().includes(q) ||
      (s.language || '').toLowerCase().includes(q) || (s.project || '').toLowerCase().includes(q)
    );
    renderList(items);
  }

  renderList(data.snippets);
  toolbar.querySelectorAll(".snippet-filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      currentFilter = btn.dataset.filter;
      toolbar.querySelectorAll(".snippet-filter-btn").forEach(b => b.classList.toggle("active", b === btn));
      applyFilters();
    });
  });
  container.querySelector("#snippet-search")?.addEventListener("input", applyFilters);
  applyLang(container);
}

// ── Insights Page (tabbed) ─────────────────────────────────────
export async function openInsights(pushHistory = true) {
  const { showView } = await import('./app.js');
  showView("insights", pushHistory);
  bindInsightsTabs();
  loadInsightsTab(state.insightsActiveTab);
}

let _insightsTabsBound = false;
export function bindInsightsTabs() {
  if (_insightsTabsBound) return;
  _insightsTabsBound = true;
  document.querySelectorAll(".insights-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      state.insightsActiveTab = tab.dataset.tab;
      document.querySelectorAll(".insights-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === state.insightsActiveTab));
      loadInsightsTab(state.insightsActiveTab);
    });
  });
}

export async function loadInsightsTab(tab) {
  const body = document.getElementById("insights-body");
  if (!body) return;
  body.innerHTML = '<div class="insights-loading"><div class="skeleton-block"></div><div class="skeleton-block" style="width:80%"></div><div class="skeleton-block" style="width:60%"></div></div>';

  try {
    if (tab === "hotspots" || tab === "heatmap" || tab === "errors") {
      if (!state.insightsDataCache.analytics) {
        state.insightsDataCache.analytics = await api("/api/analytics");
      }
      const data = state.insightsDataCache.analytics;
      body.innerHTML = "";
      if (tab === "hotspots") renderHotspotsSection(body, data);
      else if (tab === "heatmap") renderHeatmapSection(body, data);
      else renderErrorsSection(body, data);
    } else if (tab === "health") {
      if (!state.insightsDataCache.health) {
        state.insightsDataCache.health = await api("/api/project-health");
      }
      renderProjectHealthInto(body, state.insightsDataCache.health);
    } else if (tab === "snippets") {
      if (!state.insightsDataCache.snippets) {
        state.insightsDataCache.snippets = await api("/api/snippets");
      }
      renderSnippetsInto(body, state.insightsDataCache.snippets);
    }
  } catch (err) {
    body.innerHTML = `<div style="padding:40px;text-align:center;color:#e57373">${t("insights.loadFailed", { msg: esc(err.message) })}</div>`;
    if (window.showToast) {
      window.showToast.error(t("insights.loadFailed", { msg: err.message }), 0, {
        label: t("insights.retry"),
        callback: () => loadInsightsTab(tab),
      });
    }
  }
}

// ── Re-render on locale change ──────────────────────────────────
let _insightsLocaleBound = false;
function _bindInsightsLocale() {
  if (_insightsLocaleBound) return;
  _insightsLocaleBound = true;
  window.addEventListener('localechange', () => {
    const body = document.getElementById("insights-body");
    if (body && body.offsetParent !== null) {
      // Re-render the currently active tab
      loadInsightsTab(state.insightsActiveTab);
    }
  });
}
_bindInsightsLocale();
