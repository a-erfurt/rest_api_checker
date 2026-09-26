'use strict';
// Presentation controls only: no scientific calculation, execution or write API.
const body = document.body;
const sidebarToggle = document.getElementById('sidebar-toggle');
sidebarToggle?.addEventListener('click', () => {
  const collapsed = body.classList.toggle('sidebar-collapsed');
  sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
  sidebarToggle.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
});
const focusToggle = document.getElementById('focus-toggle');
function setFocus(enabled) {
  body.classList.toggle('focus-mode', enabled);
  focusToggle?.setAttribute('aria-pressed', String(enabled));
  window.dispatchEvent(new Event('resize'));
}
focusToggle?.addEventListener('click', () => setFocus(true));
document.getElementById('focus-exit')?.addEventListener('click', () => setFocus(false));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') setFocus(false);
});
document.addEventListener('click', async event => {
  const button = event.target.closest('[data-copy]');
  if (!button) return;
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
    button.textContent = 'Copied';
  } catch (_) {
    button.textContent = 'Select value to copy';
  }
});
function pausePolling(message) {
  const live = document.getElementById('overview-live');
  if (!live) return;
  if (window.htmx) window.htmx.trigger(live, 'htmx:abort');
  live.removeAttribute('hx-trigger');
  if (window.htmx) window.htmx.process(live);
  let status = live.querySelector('.poll-status');
  if (!status) {
    status = document.createElement('p');
    status.className = 'poll-status notice';
    status.setAttribute('role', 'status');
    live.append(status);
  }
  status.textContent = message;
}
for (const eventName of ['htmx:responseError', 'htmx:sendError', 'htmx:timeout']) {
  document.addEventListener(eventName, () => pausePolling('Polling paused. The database or connection is unavailable; displayed values may be stale. Reload to reconnect.'));
}
const chartData = document.getElementById('chart-data');
const canvas = document.getElementById('evaluation-chart');
let chart;
if (chartData && canvas) {
  if (window.Chart) {
    const config = JSON.parse(chartData.textContent);
    config.options.plugins.tooltip = {callbacks: {
      label: context => `${context.dataset.label}: ${context.dataset.counts[context.dataIndex]}`
    }};
    chart = new Chart(canvas, config);
  } else {
    document.getElementById('chart-unavailable').hidden = false;
  }
}
window.addEventListener('beforeprint', () => chart?.resize(1050, 330));
window.addEventListener('afterprint', () => chart?.resize());
