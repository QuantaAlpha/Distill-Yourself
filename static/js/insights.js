/**
 * Insights page — analytics sub-renderers and tabbed UI.
 *
 * Usage:
 *   import { openInsights, bindInsightsTabs, loadInsightsTab, ... } from './insights.js';
 */

import { state } from './state.js';
import { esc, formatDate, api } from './utils.js';

// ── Analytics sub-renderers (used by Insights tabs) ──────────
export function renderHotspotsSection(container, data) {
  if (!data.hotspots?.length) {
    const empty = document.createElement("div");
    empty.style.cssText = "padding:40px;text-align:center;color:var(--text-muted)";
    empty.textContent = "No file hotspot data available.";
    container.appendChild(empty);
    return;
  }
  const section = document.createElement("div");
  section.className = "analytics-section";
  const maxCount = data.hotspots[0].count;
  let html = '<h3><span class="a-icon">🔥</span> File Hotspots</h3>';
  html += '<table class="hotspot-table"><thead><tr><th>File</th><th>Edits</th><th>Sessions</th><th>Frequency</th></tr></thead><tbody>';
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
    empty.textContent = "No heatmap data available.";
    container.appendChild(empty);
    return;
  }
  const section = document.createElement("div");
  section.className = "analytics-section";
  const hm = data.heatmap;
  let html = '<h3><span class="a-icon">🗓️</span> Tool Usage Heatmap <span style="font-size:11px;font-weight:400;color:var(--text-muted)">(last 30 days)</span></h3>';
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
    empty.textContent = "No error patterns found.";
    container.appendChild(empty);
    return;
  }
  const section = document.createElement("div");
  section.className = "analytics-section";
  let html = '<h3><span class="a-icon">⚠️</span> Error Patterns</h3>';
  html += '<ul class="error-list">';
  data.errors.forEach(e => {
    html += `<li class="error-item">
      <div class="error-pattern">${esc(e.pattern)}</div>
      <div class="error-meta">
        <span><strong>${e.count}</strong> occurrences</span>
        <span><strong>${e.sessionCount}</strong> sessions</span>
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
    container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted)">No project data.</div>';
    return;
  }
  const sec = document.createElement("div");
  sec.className = "analytics-section";
  let html = '<h3><span class="a-icon">🏥</span> Project Health Dashboard</h3>';
  html += `<table class="health-table"><thead><tr>
    <th>Project</th><th>Source</th><th>Sessions</th><th>Messages</th><th>Recent (7d)</th><th>Last Active</th><th>Trend</th><th>Status</th>
  </tr></thead><tbody>`;
  data.projects.forEach(p => {
    const trendIcon = p.trend === "up" ? "📈" : p.trend === "down" ? "📉" : "➡️";
    let staleClass = "fresh";
    let staleLabel = `${p.staleDays}d ago`;
    if (p.staleDays > 30) { staleClass = "stale"; staleLabel = `${p.staleDays}d`; }
    else if (p.staleDays > 7) { staleClass = "recent"; }
    else if (p.staleDays <= 1) { staleLabel = "today"; }
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
    container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted)">No code snippets found.</div>';
    return;
  }
  const appliedCount = data.snippets.filter(s => s.applied).length;
  const toolbar = document.createElement("div");
  toolbar.style.cssText = "margin-bottom:16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  toolbar.innerHTML = `
    <input type="text" id="snippet-search" placeholder="Search snippets…" style="flex:1;min-width:200px;padding:6px 12px;border:1px solid var(--border-light);border-radius:var(--radius-sm);font-size:13px;background:var(--bg-surface);outline:none">
    <button class="snippet-filter-btn active" data-filter="all">All (${data.snippets.length})</button>
    <button class="snippet-filter-btn" data-filter="applied">✅ Applied (${appliedCount})</button>
    <button class="snippet-filter-btn" data-filter="suggested">Suggested (${data.snippets.length - appliedCount})</button>`;
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
        ? '<span class="snippet-badge applied">✅ Applied</span>'
        : '<span class="snippet-badge suggested">Suggested</span>';
      card.innerHTML = `
        <div class="snippet-header">
          <span class="snippet-lang">${esc(s.language || "code")}</span>
          ${badge}
          <span class="snippet-context">${esc(s.context)}</span>
          <span class="snippet-meta">${esc(s.project)} · ${formatDate(s.date)}</span>
        </div>
        <div class="snippet-code-wrap">
          <div class="snippet-code">${esc(s.code)}</div>
          <button class="snippet-copy" title="Copy code">📋</button>
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
    body.innerHTML = `<div style="padding:40px;text-align:center;color:#e57373">Failed: ${esc(err.message)}</div>`;
  }
}
