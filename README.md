# ConvoLab

Local-first analytics platform for Claude Code & Codex conversation histories. Browse, search, analyze, and visualize your AI coding sessions — all data stays on your machine.

![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue) ![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-green) ![License](https://img.shields.io/badge/license-private-lightgrey)

## Features

### Sessions
- **Full conversation viewer** — browse all Claude Code and Codex sessions with message-level rendering (user, assistant, tool calls, thinking blocks)
- **Smart filtering** — filter by source (Claude/Codex), date range (7d/30d/90d), and project via a popover with active filter chips
- **Full-text search** — fuzzy search across all session content with highlighted results
- **Session outline** — collapsible sidebar showing user message anchors for quick navigation
- **Keyboard shortcuts** — `j/k` navigate sessions, `/` focuses search, `Enter` opens, `Esc` goes back

### Insights (5 tabs)
- **Tool Heatmap** — which tools (Bash, Read, Edit, Grep, Write, Agent…) are used most, with per-tool breakdowns
- **File Hotspots** — most frequently touched files across all sessions
- **Error Patterns** — recurring errors and failure modes with context
- **Project Health** — per-project activity scores, session counts, and trend indicators
- **Snippets** — extracted code snippets with language detection, applied/suggested status, and search

### AI Evolve (D3.js visualizations)
- **Profile Radar** — multi-axis radar chart of coding style dimensions (autonomy, complexity, tool diversity, etc.)
- **Memory Mind Map** — force-directed graph of user memory entries and their relationships
- **Rules Force Graph** — interactive network of project rules (CLAUDE.md) and their connections
- **Signals Timeline** — temporal scatter plot of behavioral signals (style shifts, preference changes)
- **Behavior Patterns** — clustered pattern visualization with evolution tracking

### AI Chat
- **Session-scoped analysis** — ask questions about any specific session ("What was the main bug here?")
- **Global analysis** — ask questions across all sessions ("Which project had the most errors this week?")
- **Chat history** — persistent conversation history with localStorage caching

## Quick Start

```bash
# Clone
git clone https://github.com/QuantaAlpha/ConvoLab.git
cd ConvoLab

# Run (no install needed — zero dependencies)
python3 server.py

# Open
open http://localhost:8080
```

### Requirements

- **Python 3.8+** (stdlib only, no pip install)
- **Claude Code** or **Codex** session data in `~/.claude/projects/` or `~/.codex/sessions/`
- A modern browser (Chrome, Safari, Firefox, Edge)

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `PORT` | `8080` | Server port |
| `ANTHROPIC_API_KEY` | — | Required for AI chat features |

## Architecture

```
ConvoLab/
├── server.py          # Python HTTP server + all API endpoints + AI chat
├── analyze.py         # CLI analytics tool (standalone)
├── start.sh           # Quick launcher script
└── static/
    ├── index.html     # SPA shell (sidebar nav + content views)
    ├── app.js         # Core app logic (~2000 lines vanilla JS)
    ├── evolve.js      # D3.js visualizations for AI Evolve page
    └── style.css      # Full stylesheet (light premium theme)
```

### Design Principles

- **Zero dependencies** — Python stdlib for the server, vanilla JS for the frontend. Only external resource is D3.js via CDN.
- **Privacy first** — all data stays local. Session files are read directly from `~/.claude/projects/`. No telemetry, no external calls (except optional AI chat via Anthropic API).
- **Single file server** — `server.py` handles static files, API routes, JSONL parsing, caching, and AI chat in one file.
- **Incremental indexing** — session index is built on startup and cached to `.cache/index.json`. Only changed files are re-parsed on refresh.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/sessions` | List all sessions (id, title, date, source, project) |
| `GET /api/session/:id` | Full session messages |
| `GET /api/projects` | List all projects |
| `GET /api/search?q=...` | Full-text search across sessions |
| `GET /api/timeline` | Daily session counts (for heatmaps) |
| `GET /api/analytics` | Tool usage analytics |
| `GET /api/insights` | File hotspots + error patterns |
| `GET /api/project-health` | Per-project health scores |
| `GET /api/snippets` | Extracted code snippets |
| `GET /api/evolve/:tab` | AI Evolve data (profile/memory/rules/signals/patterns) |
| `GET /api/stats` | Global statistics |
| `POST /api/chat` | AI chat (requires ANTHROPIC_API_KEY) |
| `POST /api/refresh` | Rebuild session index |

## CLI Analytics

```bash
# Run standalone analytics on your sessions
python3 analyze.py

# With AI-enhanced analysis (requires API key)
ANTHROPIC_API_KEY=sk-... python3 analyze.py --ai
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `Esc` | Clear search / go back |
| `j` / `k` | Next / previous session |
| `Enter` | Open selected session |
| `n` / `N` | Next / previous user message |
| `h` | Go to sessions list |
| `o` | Toggle session outline |
| `c` | Open AI chat for current session |
| `1` / `2` / `3` | Switch to Sessions / AI Evolve / Insights |
| `?` | Show keyboard help |

## License

Private. All rights reserved.
