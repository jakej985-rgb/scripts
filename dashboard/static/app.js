/* app.js — M3TAL Dashboard v2 */

const socket = io();

// ── Clock ────────────────────────────────────────────────────────
function tick() {
    const el = document.getElementById('live-clock');
    if (!el) return;
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    el.textContent = `${hh}:${mm}:${ss}`;
}
setInterval(tick, 1000);
tick();

// ── Resource Chart ───────────────────────────────────────────────
let chart = null;
const MAX_POINTS = 30;
const cpuData  = Array(MAX_POINTS).fill(null);
const memData  = Array(MAX_POINTS).fill(null);
const timeLabels = Array(MAX_POINTS).fill('');

function initChart() {
    const canvas = document.getElementById('resource-chart');
    if (!canvas) return;

    chart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: timeLabels,
            datasets: [
                {
                    label: 'CPU',
                    data: cpuData,
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34,197,94,0.08)',
                    borderWidth: 1.5,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                },
                {
                    label: 'MEM',
                    data: memData,
                    borderColor: '#a855f7',
                    backgroundColor: 'rgba(168,85,247,0.08)',
                    borderWidth: 1.5,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    display: false,
                    grid: { display: false }
                },
                y: {
                    min: 0, max: 100,
                    grid: { color: 'rgba(255,255,255,0.04)', drawBorder: false },
                    ticks: {
                        color: '#4b5e75',
                        font: { family: "'JetBrains Mono', monospace", size: 10 },
                        callback: v => `${v}%`,
                        maxTicksLimit: 5,
                    },
                    border: { display: false }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(13,17,23,0.9)',
                    borderColor: 'rgba(0,212,170,0.2)',
                    borderWidth: 1,
                    titleColor: '#94a3b8',
                    bodyColor: '#e2e8f0',
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
                }
            }
        }
    });
}

function pushChartPoint(cpu, mem) {
    if (!chart) return;
    const now = new Date();
    const label = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

    cpuData.push(cpu);
    memData.push(mem);
    timeLabels.push(label);

    if (cpuData.length > MAX_POINTS)   { cpuData.shift(); }
    if (memData.length > MAX_POINTS)   { memData.shift(); }
    if (timeLabels.length > MAX_POINTS){ timeLabels.shift(); }

    chart.update('none');
}

// ── Socket – real-time metrics ────────────────────────────────────
socket.on('metrics_update', (data) => {
    const sys = data.system || {};
    const cpu = sys.cpu || 0;
    const mem = sys.mem || 0;

    // Stat cards
    setText('stat-cpu', `${cpu.toFixed(1)}%`);
    setText('stat-mem', `${(sys.mem_gb || 0).toFixed(1)} GB`);

    // Push to chart
    pushChartPoint(cpu, mem);
});

// ── Helpers ───────────────────────────────────────────────────────
function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function getStatusClass(status) {
    const s = (status || '').toLowerCase();
    if (s === 'running' || s === 'online') return 'running';
    if (s === 'restarting') return 'restarting';
    if (s === 'offline' || s === 'exited') return 'offline';
    if (s === 'missing') return 'missing';
    return 'unknown';
}

function getCpuClass(cpu) {
    if (cpu >= 80) return 'cpu-crit';
    if (cpu >= 50) return 'cpu-high';
    return '';
}

// ── Health score ──────────────────────────────────────────────────
async function refreshHealth() {
    try {
        const res  = await fetch('/api/health/report');
        const data = await res.json();
        const score = data.score || 0;
        const verdict = data.verdict || 'Healthy';

        setText('health-score', score);
        const ring = document.getElementById('health-ring');
        if (ring) {
            const offset = 220 - (220 * score / 100);
            ring.style.strokeDashoffset = offset;
        }

        const verdictEl = document.getElementById('system-verdict');
        if (verdictEl) {
            verdictEl.textContent = verdict.toUpperCase();
            verdictEl.className = `badge ${score >= 80 ? 'running' : score >= 50 ? 'restarting' : 'offline'}`;
        }
    } catch (_) {}
}

// ── Container table ───────────────────────────────────────────────
async function refreshFleet() {
    try {
        const [hRes, mRes] = await Promise.all([
            fetch('/api/health/report'),
            fetch('/api/metrics')
        ]);
        const hData = await hRes.json();
        const mData = await mRes.json();

        // Build metrics lookup
        const metricsByName = {};
        (mData.containers || []).forEach(c => {
            metricsByName[c.name] = c;
            metricsByName[c.name.replace('m3tal-', '')] = c;
        });

        const containers = hData?.agent_health?.monitor_containers?.containers || {};
        const entries = Object.entries(containers);

        // Stat cards
        const online  = entries.filter(([,v]) => ['online','running'].includes((v.status||'').toLowerCase())).length;
        const total   = entries.length;
        setText('stat-containers-val', `${online} / ${total}`);
        setText('stat-containers-sub', 'Running');

        // Uptime
        const uptimeEl = document.getElementById('stat-uptime');
        if (uptimeEl && hData.uptime) uptimeEl.textContent = hData.uptime;

        // Table body
        const tbody = document.getElementById('fleet-tbody');
        if (!tbody) return;

        if (entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-text">Waiting for agent data…</td></tr>';
            return;
        }

        // Sort: running first
        const order = { running: 0, online: 0, restarting: 1, offline: 2, missing: 3, unknown: 4 };
        entries.sort((a, b) => (order[(a[1].status||'').toLowerCase()] ?? 4) - (order[(b[1].status||'').toLowerCase()] ?? 4));

        tbody.innerHTML = entries.map(([name, info]) => {
            const status = info.status || 'unknown';
            const sc     = getStatusClass(status);
            const m      = metricsByName[name] || {};
            const cpu    = m.cpu  != null ? m.cpu.toFixed(1)  + '%' : '—';
            const mem    = m.mem_usage || '—';
            const uptime = info.raw_status || '—';
            const cpuClass = m.cpu != null ? getCpuClass(m.cpu) : '';

            return `
                <tr>
                    <td><span class="container-name">${name}</span></td>
                    <td><span class="badge ${sc}">${status.toUpperCase()}</span></td>
                    <td class="metric-cell ${cpuClass}">${cpu}</td>
                    <td class="metric-cell">${mem}</td>
                    <td class="metric-cell">${uptime}</td>
                    <td>
                        <div class="actions-cell">
                            <button class="action-btn restart" title="Restart" onclick="doAction('restart','${name}')">↺</button>
                            <button class="action-btn logs"    title="Logs"    onclick="doAction('logs','${name}')">≡</button>
                            <button class="action-btn stop"    title="Stop"    onclick="doAction('stop','${name}')">■</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (_) {}
}

// ── Activity feed ─────────────────────────────────────────────────
async function refreshActivity() {
    try {
        const [aRes, hRes] = await Promise.all([
            fetch('/api/anomalies'),
            fetch('/api/health/report')
        ]);
        const aData = await aRes.json();
        const hData = await hRes.json();

        const feed = document.getElementById('activity-feed');
        if (!feed) return;

        const issues = [
            ...(aData.issues || []).map(i => ({
                title: i.target || 'Container',
                sub:   i.reason || i.message || '',
                type:  (i.type === 'critical') ? 'warn' : 'warn',
                time:  formatTime()
            })),
            ...(hData.issues || []).map(msg => ({
                title: 'System',
                sub:   msg,
                type:  'warn',
                time:  formatTime()
            }))
        ];

        const now = formatTime();

        const pinned = [{
            title: issues.length === 0 ? 'All systems operational' : `${issues.length} issue(s) detected`,
            sub:   issues.length === 0 ? 'No issues detected'       : 'Review anomalies below',
            type:  issues.length === 0 ? 'ok' : 'warn',
            time:  now
        }];

        const all = [...pinned, ...issues].slice(0, 8);

        const iconMap = { ok: '✓', warn: '⚠', info: 'ℹ' };

        feed.innerHTML = all.map(item => `
            <div class="activity-item">
                <div class="activity-icon ${item.type}">${iconMap[item.type] || 'ℹ'}</div>
                <div class="activity-text">
                    <div class="activity-title">${item.title}</div>
                    ${item.sub ? `<div class="activity-sub">${item.sub}</div>` : ''}
                </div>
                <div class="activity-time">${item.time}</div>
            </div>
        `).join('');
    } catch (_) {}
}

function formatTime() {
    const n = new Date();
    return `${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}`;
}

// ── Actions (wired to /api/action) ───────────────────────────
async function doAction(action, container) {
    console.log(`Action: ${action} on ${container}`);
    const btn = event.currentTarget;
    const origHtml = btn.innerHTML;
    btn.innerHTML = '⏳';
    btn.disabled = true;

    try {
        const res = await fetch('/api/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action, container })
        });
        const data = await res.json();
        
        if (data.ok) {
            if (action === 'logs' && data.logs) {
                // Show logs in an alert or custom overlay
                alert(`Logs for ${container}:\n\n${data.logs.substring(0, 1000)}${data.logs.length > 1000 ? '...' : ''}`);
            } else {
                btn.style.background = 'var(--green-dim)';
                btn.style.color = 'var(--green)';
                setTimeout(() => {
                    btn.style.background = '';
                    btn.style.color = '';
                }, 2000);
            }
        } else {
            alert(`Error: ${data.error || 'Failed'}`);
            btn.style.background = 'var(--red-dim)';
            btn.style.color = 'var(--red)';
        }
    } catch (e) {
        alert(`Request failed: ${e.message}`);
    } finally {
        setTimeout(() => {
            btn.innerHTML = origHtml;
            btn.disabled = false;
        }, action === 'logs' ? 0 : 2000);
    }
}

async function doGlobalAction(action) {
    console.log(`Global action: ${action}`);
    
    // Add confirmation for reboot
    if (action === 'reboot' && !confirm('Are you sure you want to reboot the entire host system?')) {
        return;
    }

    const btn = event.currentTarget;
    const origHtml = btn.innerHTML;
    btn.innerHTML = '⏳ Processing...';
    btn.disabled = true;

    try {
        const res = await fetch('/api/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ action })
        });
        const data = await res.json();
        
        if (data.ok) {
            if (action === 'status') {
                 alert(`Status:\nScore: ${data.score}%\nVerdict: ${data.verdict}\nSystem: ${data.system}`);
            } else {
                 btn.innerHTML = `✅ ${data.message || 'Success'}`;
            }
        } else {
            alert(`Error: ${data.error || 'Failed'}`);
            btn.innerHTML = '❌ Error';
        }
    } catch (e) {
        alert(`Request failed: ${e.message}`);
        btn.innerHTML = '❌ Failed';
    } finally {
        setTimeout(() => {
            btn.innerHTML = origHtml;
            btn.disabled = false;
        }, 3000);
    }
}

// ── Boot ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Telegram Web App Initialization
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
    }

    initChart();
    refreshHealth();
    refreshFleet();
    refreshActivity();

    setInterval(refreshHealth,   5000);
    setInterval(refreshFleet,    8000);
    setInterval(refreshActivity, 12000);
});
