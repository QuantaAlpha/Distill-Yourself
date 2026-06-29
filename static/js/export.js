/**
 * Export functionality — exportMarkdown, copyConversation.
 *
 * Usage:
 *   import { exportMarkdown, copyConversation } from './export.js';
 */

import { state } from './state.js';
import { dom, $ } from './dom.js';

// ── Markdown Export (F4) ──────────────────────────────────────
export function exportMarkdown() {
  if (!state.currentMessages.length || !state.currentSessionId) return;

  const title = dom.convTitle.textContent || "Untitled";
  const meta = dom.convMeta.textContent || "";
  let md = `# ${title}\n\n_${meta}_\n\n---\n\n`;

  for (const msg of state.currentMessages) {
    if (msg.type === "user") {
      const text = msg.content.map(b => b.type === "text" ? b.text : "").join("\n").trim();
      if (text) md += `## 👤 You\n\n${text}\n\n`;
    } else if (msg.type === "assistant") {
      for (const block of msg.content) {
        if (block.type === "text" && block.text?.trim()) {
          md += `### 🤖 Assistant\n\n${block.text}\n\n`;
        } else if (block.type === "tool_use") {
          const inp = typeof block.input === "string" ? block.input : JSON.stringify(block.input, null, 2);
          md += `<details><summary>🔧 ${block.name}</summary>\n\n\`\`\`json\n${inp}\n\`\`\`\n</details>\n\n`;
        } else if (block.type === "thinking") {
          md += `<details><summary>💭 Thinking</summary>\n\n${block.text}\n</details>\n\n`;
        }
      }
    } else if (msg.type === "tool_result") {
      const content = msg.content.map(b => typeof b.content === "string" ? b.content : JSON.stringify(b.content)).join("\n");
      if (content.trim()) {
        md += `<details><summary>📋 Tool Result</summary>\n\n\`\`\`\n${content.substring(0, 2000)}\n\`\`\`\n</details>\n\n`;
      }
    }
  }

  // Trigger download
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.substring(0, 60).replace(/[\/\\?%*:|"<>]/g, "_")}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Copy Conversation (User + Assistant text only) ─────────────
export function copyConversation() {
  if (!state.currentMessages.length) return;
  let text = "";
  for (const msg of state.currentMessages) {
    if (msg.type === "user") {
      const t = msg.content.map(b => b.type === "text" ? b.text : "").join("\n").trim();
      if (t) text += `👤 You:\n${t}\n\n`;
    } else if (msg.type === "assistant") {
      const t = msg.content.filter(b => b.type === "text" && b.text?.trim()).map(b => b.text).join("\n\n");
      if (t) text += `🤖 Assistant:\n${t}\n\n`;
    }
  }
  navigator.clipboard.writeText(text.trim()).then(() => {
    const btn = $("#btn-copy-conv");
    const orig = btn.innerHTML;
    btn.innerHTML = "✅ Copied";
    setTimeout(() => { btn.innerHTML = orig; }, 1500);
  });
}
