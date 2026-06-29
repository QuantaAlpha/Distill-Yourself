/**
 * DOM helpers and cached element references.
 *
 * Usage:
 *   import { $, $$, dom, initDom } from './dom.js';
 *   // call initDom() once after DOMContentLoaded
 */

export const $ = (sel) => document.querySelector(sel);
export const $$ = (sel) => document.querySelectorAll(sel);

export let dom = {};

export function initDom() {
  dom = {
    searchInput: $("#global-search"),
    searchStats: $("#search-stats"),
    projectTrigger: $("#project-trigger"),
    projectDropdown: $("#project-dropdown"),
    sessionList: $("#session-list"),
    sessionCount: $("#session-count"),
    convView: $("#conversation-view"),
    searchResults: $("#search-results"),
    messagesContainer: $("#messages-container"),
    convTitle: $("#conv-title"),
    convMeta: $("#conv-meta"),
    searchResultCount: $("#search-result-count"),
    searchResultsList: $("#search-results-list"),
    searchSortSelect: $("#search-sort"),
    rightPanel: $("#right-panel"),
    outlineList: $("#outline-list"),
    insightsView: $("#insights-view"),
    aiView: $("#ai-view"),
    sidebar: $("#sidebar"),
    kbdHelp: $("#kbd-help"),
  };
  return dom;
}
