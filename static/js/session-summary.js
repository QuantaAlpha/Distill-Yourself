/**
 * Session summary — load and render session summary (Request vs Reality).
 *
 * Usage:
 *   import { loadSessionSummary, renderSessionSummary } from './session-summary.js';
 */

import { esc, api } from './utils.js';

// ── F11: Session Summary (Request vs Reality) ──────────────────
export async function loadSessionSummary(sessionId) {
  const body = document.getElementById("summary-body");
  if (!body) return;
  body.innerHTML = '<div style="padding:12px;font-size:12px;color:var(--text-muted)">Loading…</div>';

  try {
    const data = await api(`/api/session-summary?session=${sessionId}`);
    renderSessionSummary(data, body);
  } catch (err) {
    body.innerHTML = '<div style="padding:12px;font-size:12px;color:var(--text-muted)">—</div>';
  }
}

export function renderSessionSummary(data, body) {
  body.innerHTML = "";
  // Request
  if (data.request) {
    const sec = document.createElement("div");
    sec.className = "insight-section";
    sec.innerHTML = `<h4>📝 Initial Request</h4><div class="summary-request">${esc(data.request)}</div>`;
    body.appendChild(sec);
  }
  // Files touched
  if (data.files?.length) {
    const sec = document.createElement("div");
    sec.className = "insight-section";
    let html = `<h4>📁 Files Touched (${data.files.length})</h4><ul class="summary-files">`;
    data.files.forEach(f => {
      const badges = [];
      if (f.edits) badges.push(`<span class="sf-badge edit">${f.edits} edit</span>`);
      if (f.writes) badges.push(`<span class="sf-badge write">${f.writes} write</span>`);
      if (f.reads) badges.push(`<span class="sf-badge read">${f.reads} read</span>`);
      html += `<li class="summary-file"><span class="sf-path" title="${esc(f.path)}">${esc(f.path)}</span>${badges.join("")}</li>`;
    });
    html += '</ul>';
    sec.innerHTML = html;
    body.appendChild(sec);
  }
  // Tool summary
  if (data.tools && Object.keys(data.tools).length) {
    const sec = document.createElement("div");
    sec.className = "insight-section";
    const sorted = Object.entries(data.tools).sort((a, b) => b[1] - a[1]);
    let html = '<h4>🔧 Tool Usage</h4><div style="display:flex;gap:6px;flex-wrap:wrap">';
    sorted.forEach(([name, count]) => {
      html += `<span style="font-size:11px;padding:3px 7px;background:var(--bg-surface2);border-radius:10px">${esc(name)} <strong>${count}</strong></span>`;
    });
    html += '</div>';
    sec.innerHTML = html;
    body.appendChild(sec);
  }
}
