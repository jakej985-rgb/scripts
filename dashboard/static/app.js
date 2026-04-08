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
    const res = await fetch('/api/health'); // This should point to health_report.json
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
    const res = await fetch('/api/health'); // raw health.json
    const data = await res.json();
    
    containerList.innerHTML = '';
    for (const [name, info] of Object.entries(data)) {
        if (name === 'score' || name === 'verdict' || name.startsWith('_')) continue;
        
        const item = document.createElement('div');
        item.className = 'container-item';
        item.innerHTML = `
            <div class="name">${name}</div>
            <div class="status-pill ${info.status.toLowerCase()}">${info.status}</div>
        `;
        containerList.appendChild(item);
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
