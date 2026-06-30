/**
 * Lightweight toast notification system.
 *
 * Usage (module):
 *   import { showToast } from './toast.js';
 *   showToast('Saved successfully', 'success');
 *   showToast.error('Something went wrong');
 *
 * Usage (global):
 *   window.showToast('Hello', 'info');
 *   window.showToast.success('Done');
 *
 * Types: 'success' | 'error' | 'warning' | 'info'
 * Duration: ms (0 = persistent, must be closed manually)
 */

const TOAST_ICONS = {
  success: '✓',
  error: '✕',
  warning: '!',
  info: 'i',
};

let _container = null;

function _ensureContainer() {
  if (_container && document.body.contains(_container)) return _container;
  _container = document.createElement('div');
  _container.className = 'toast-container';
  _container.setAttribute('role', 'region');
  _container.setAttribute('aria-live', 'polite');
  document.body.appendChild(_container);
  return _container;
}

/**
 * Show a toast notification.
 * @param {string} message - The message text
 * @param {string} [type='info'] - 'success' | 'error' | 'warning' | 'info'
 * @param {number} [duration=3000] - Auto-dismiss time in ms; 0 = persistent
 */
export function showToast(message, type = 'info', duration = 3000) {
  const container = _ensureContainer();
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

  const icon = TOAST_ICONS[type] || TOAST_ICONS.info;
  toast.innerHTML = `
    <span class="toast-icon" aria-hidden="true">${icon}</span>
    <span class="toast-message"></span>
    <button type="button" class="toast-close-btn" aria-label="Close">×</button>
  `;
  // Use textContent for message to prevent XSS
  toast.querySelector('.toast-message').textContent = String(message || '');

  const closeBtn = toast.querySelector('.toast-close-btn');
  let _dismissed = false;

  function dismiss() {
    if (_dismissed) return;
    _dismissed = true;
    toast.classList.add('toast-exit');
    // Wait for exit animation before removing
    const remove = () => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    };
    toast.addEventListener('animationend', remove, { once: true });
    // Fallback in case animationend doesn't fire
    setTimeout(remove, 400);
  }

  closeBtn.addEventListener('click', dismiss);

  // Enter animation — trigger on next frame so transition applies
  requestAnimationFrame(() => {
    toast.classList.add('toast-enter');
  });

  container.appendChild(toast);

  // Auto-dismiss
  if (duration > 0) {
    setTimeout(dismiss, duration);
  }

  return { dismiss };
}

// Convenience methods
showToast.success = (msg, duration) => showToast(msg, 'success', duration);
showToast.error = (msg, duration) => showToast(msg, 'error', duration);
showToast.warning = (msg, duration) => showToast(msg, 'warning', duration);
showToast.info = (msg, duration) => showToast(msg, 'info', duration);

// Expose for non-module scripts
window.showToast = showToast;
