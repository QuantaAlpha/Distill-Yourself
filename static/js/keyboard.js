/**
 * Keyboard navigation — global keydown handler, session/message navigation, outline.
 *
 * Usage:
 *   import { handleKeyboard, navigateSession, navigateUserMessage,
 *            toggleOutline, buildOutline, highlightOutlineItem } from './keyboard.js';
 */

import { state } from './state.js';
import { dom } from './dom.js';
import { esc } from './utils.js';
import { jumpToMessage } from './search.js';
import { openInsights } from './insights.js';

// ── Keyboard Navigation (F5) ────────────────────────────────────
export function handleKeyboard(e) {
  const tag = document.activeElement?.tagName;
  const isInput = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

  // ? — help overlay (always works)
  if (e.key === "?" && !isInput) {
    e.preventDefault();
    dom.kbdHelp.classList.toggle("hidden");
    return;
  }
  // Esc — close help, blur search, or go home
  if (e.key === "Escape") {
    if (!dom.kbdHelp.classList.contains("hidden")) { dom.kbdHelp.classList.add("hidden"); return; }
    if (isInput) { dom.searchInput.blur(); dom.searchInput.value = ""; return; }
    import('./app.js').then(m => m.showView("sessions"));
    return;
  }
  // Don't handle when typing in input
  if (isInput) {
    if (e.key === "/" && document.activeElement === dom.searchInput) return;
    return;
  }

  // Don't intercept shortcuts with modifier keys (Ctrl+C, Cmd+V, etc.)
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  // Don't intercept when user has text selected (allow native copy/select)
  if (window.getSelection && window.getSelection().toString()) return;

  switch (e.key) {
    case "/":
      e.preventDefault();
      dom.searchInput.focus();
      break;
    case "j": // next session
      navigateSession(1);
      break;
    case "k": // prev session
      navigateSession(-1);
      break;
    case "Enter": { // open selected session
      const active = dom.sessionList.querySelector("li.active");
      if (active) {
        import('./app.js').then(m => m.loadSession(active.dataset.id));
      }
      break;
    }
    case "h": // go back
      import('./app.js').then(m => m.showView("sessions"));
      break;
    case "n": // next user message
      navigateUserMessage(1);
      break;
    case "N": // prev user message
      navigateUserMessage(-1);
      break;
    case "1": // Sessions
      import('./app.js').then(m => m.showView("sessions"));
      break;
    case "2": // AI Evolve
      import('./app.js').then(m => { m.showView("ai"); m.initAiPage(); });
      break;
    case "3": // Insights
      openInsights();
      break;
    case "4": // Digital Twin
      import('./app.js').then(m => m.showView("twin"));
      break;
    case "o": // outline
      if (!dom.convView.classList.contains("hidden")) toggleOutline();
      break;
    case "c": // ask AI about session
      if (!dom.convView.classList.contains("hidden")) {
        import('./app.js').then(m => m.openSessionAiPanel());
      }
      break;
  }
}

export function navigateSession(direction) {
  const items = Array.from(dom.sessionList.querySelectorAll("li"));
  if (!items.length) return;
  const activeIdx = items.findIndex(li => li.classList.contains("active"));
  let nextIdx = activeIdx + direction;
  if (nextIdx < 0) nextIdx = 0;
  if (nextIdx >= items.length) nextIdx = items.length - 1;
  items.forEach(li => li.classList.remove("active"));
  items[nextIdx].classList.add("active");
  items[nextIdx].scrollIntoView({ block: "nearest" });
}

export function navigateUserMessage(direction) {
  const container = document.getElementById("messages-container");
  if (!container) return;
  const userMsgs = Array.from(container.querySelectorAll(".msg.user-msg"));
  if (!userMsgs.length) return;

  // Find which user message is currently in view
  const containerRect = container.getBoundingClientRect();
  const viewCenter = containerRect.top + containerRect.height / 3;
  let currentIdx = -1;
  for (let i = 0; i < userMsgs.length; i++) {
    const r = userMsgs[i].getBoundingClientRect();
    if (r.top >= viewCenter - 20) { currentIdx = i; break; }
  }
  if (currentIdx === -1) currentIdx = userMsgs.length - 1;

  let targetIdx = direction > 0 ? currentIdx + 1 : currentIdx - 1;
  // Ensure forward actually moves past current
  if (direction > 0 && currentIdx >= 0) {
    const r = userMsgs[currentIdx].getBoundingClientRect();
    if (r.top < viewCenter + 20) targetIdx = currentIdx + 1;
    else targetIdx = currentIdx;
  }
  if (targetIdx < 0) targetIdx = 0;
  if (targetIdx >= userMsgs.length) targetIdx = userMsgs.length - 1;

  userMsgs[targetIdx].scrollIntoView({ behavior: "smooth", block: "start" });
  // Highlight in outline
  highlightOutlineItem(parseInt(userMsgs[targetIdx].dataset.idx));
}

// ── Outline Panel (F2) ────────────────────────────────────────
export function toggleOutline() {
  // Panel is always visible; toggle switches to Outline tab
  const current = document.querySelector(".rp-tab.active")?.dataset.panel;
  const target = current === "outline" ? "ai" : "outline";
  document.querySelectorAll(".rp-tab").forEach(t => t.classList.toggle("active", t.dataset.panel === target));
  document.querySelectorAll(".rp-content").forEach(c => c.classList.toggle("hidden", !c.id.endsWith(target)));
}

export function buildOutline(messages) {
  dom.outlineList.innerHTML = "";
  let userIdx = 0;
  messages.forEach((msg, i) => {
    if (msg.type !== "user") return;
    const text = msg.content.map(b => b.type === "text" ? b.text : "").join(" ").trim();
    if (!text) return;
    userIdx++;
    const li = document.createElement("li");
    li.dataset.msgIdx = i;
    li.innerHTML = `<span class="outline-idx">${userIdx}</span>${esc(text.substring(0, 80))}`;
    li.addEventListener("click", () => {
      jumpToMessage(i);
      highlightOutlineItem(i);
    });
    dom.outlineList.appendChild(li);
  });
}

export function highlightOutlineItem(msgIdx) {
  dom.outlineList.querySelectorAll("li").forEach(li => {
    li.classList.toggle("active", parseInt(li.dataset.msgIdx) === msgIdx);
  });
}
