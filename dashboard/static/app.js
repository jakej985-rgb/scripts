const socket = io();

// UI Elements
const healthScore = document.getElementById('health-score');
const healthMeter = document.getElementById('health-meter');
const cpuVal = document.getElementById('cpu-val');
const cpuFill = document.getElementById('cpu-fill');
const memVal = document.getElementById('mem-val');
const memFill = document.getElementById('mem-fill');
const containerList = document.getElementById('container-list');
const anomalyFeed = document.getElementById('anomaly-feed');

// 1. Initial Load
async function init() {
    refreshHealth();
    refreshAnomalies();
    refreshFleet();
}

async function refreshHealth() {
    const res = await fetch('/api/health/report'); // Use report for score/verdict (Audit Fix 6.6)
    const data = await res.json();
    
    if (data.score !== undefined) {
        healthScore.innerText = data.score;
        const offset = 283 - (283 * data.score / 100);
        healthMeter.style.strokeDashoffset = offset;
        
        const verdictPill = document.querySelector('#system-verdict span');
        verdictPill.innerText = data.verdict || "Healthy";
        verdictPill.className = `status-pill ${(data.verdict || "Healthy").toLowerCase()}`;
    }
}

async function refreshFleet() {
    const res = await fetch('/api/health/report'); // Use report for containers
    const data = await res.json();
    
    containerList.innerHTML = '';
    
    // Safely extract the container list from the new M3TAL v1.3 agent structure
    const containers = data?.agent_health?.monitor_containers?.containers || {};
    const entries = Object.entries(containers);

    const online = entries.filter(([,v]) => v.status === 'online').length;
    const offline = entries.filter(([,v]) => v.status === 'offline').length;
    const missing = entries.filter(([,v]) => v.status === 'missing').length;
    const total = entries.length;

    // 1. Build the summary header
    const summaryItem = document.createElement('div');
    summaryItem.style.display = 'flex';
    summaryItem.style.justifyContent = 'space-between';
    summaryItem.style.padding = '1rem';
    summaryItem.style.background = 'rgba(0,0,0,0.2)';
    summaryItem.style.borderRadius = '8px';
    summaryItem.style.marginBottom = '1rem';
    
    summaryItem.innerHTML = `
        <div style="text-align: center">
            <div style="font-size: 1.25rem; font-weight: 800">${total}</div>
            <div style="font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase">Total</div>
        </div>
        <div style="text-align: center">
            <div style="font-size: 1.25rem; font-weight: 800; color: var(--success)">${online}</div>
            <div style="font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase">Online</div>
        </div>
        <div style="text-align: center">
            <div style="font-size: 1.25rem; font-weight: 800; color: var(--danger)">${offline}</div>
            <div style="font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase">Offline</div>
        </div>
        <div style="text-align: center">
            <div style="font-size: 1.25rem; font-weight: 800; color: var(--warning)">${missing}</div>
            <div style="font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase">Missing</div>
        </div>
    `;
    containerList.appendChild(summaryItem);
    
    // 2. Determine failing containers
    const failing = entries.filter(([,v]) => v.status !== 'online');
    
    if (failing.length === 0 && total > 0) {
        // All good
        const msg = document.createElement('div');
        msg.style.textAlign = 'center';
        msg.style.padding = '1.5rem 0';
        msg.style.fontSize = '0.9rem';
        msg.style.color = 'var(--text-secondary)';
        msg.innerHTML = '<span style="color:var(--success); margin-right: 0.25rem">✓</span> All containers healthy';
        containerList.appendChild(msg);
    } else {
        // List failing containers
        for (const [name, info] of failing) {
            const item = document.createElement('div');
            item.className = 'container-item';
            const status = info.status || "unknown";
            item.innerHTML = `
                <div class="name">${name}</div>
                <div class="status-pill ${status.toLowerCase()}">${status}</div>
            `;
            containerList.appendChild(item);
        }
    }
}

async function refreshAnomalies() {
    const res = await fetch('/api/anomalies');
    const data = await res.json();
    
    anomalyFeed.innerHTML = '';
    (data.issues || []).forEach(issue => {
        const item = document.createElement('div');
        item.className = 'container-item';
        item.innerHTML = `
            <div class="info">
                <div class="target">${issue.target}</div>
                <div class="reason" style="font-size: 0.75rem; color: var(--text-secondary)">${issue.reason}</div>
            </div>
            <div class="type status-pill ${issue.type === 'critical' ? 'offline' : 'loading'}">${issue.type}</div>
        `;
        anomalyFeed.appendChild(item);
    });
}

// 2. WebSocket Updates
socket.on('metrics_update', (data) => {
    const sys = data.system || {};
    cpuVal.innerText = `${(sys.cpu || 0).toFixed(1)}%`;
    cpuFill.style.width = `${sys.cpu || 0}%`;
    
    memVal.innerText = `${(sys.mem_gb || 0).toFixed(1)} GB`;
    memFill.style.width = `${sys.mem || 0}%`;
});

// Periodic refresh
setInterval(refreshHealth, 5000);
setInterval(refreshFleet, 5000);
setInterval(refreshAnomalies, 10000);

init();
