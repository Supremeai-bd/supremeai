// admin/dashboard/script.js

// ════════════════════════════════════════════════════════════
// 1. CONFIGURATION & STATE
// ════════════════════════════════════════════════════════════
const REPO = 'paykaribazaronline/supremeai';
const BRANCH = 'main';
const RAW_URL = `https://raw.githubusercontent.com/${REPO}/${BRANCH}`;
const API_BASE = ''; // e.g., 'http://localhost:8000' if running separately

// ════════════════════════════════════════════════════════════
// 2. NAVIGATION LOGIC
// ════════════════════════════════════════════════════════════
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelectorAll('.view-section').forEach(v => v.classList.add('hidden'));
        
        e.currentTarget.classList.add('active');
        document.getElementById(e.currentTarget.getAttribute('data-target')).classList.remove('hidden');
    });
});

// ════════════════════════════════════════════════════════════
// 3. FETCH LIVE CI/CD PIPELINES (GitHub Raw)
// ════════════════════════════════════════════════════════════
async function fetchLiveJobs() {
    try {
        const res = await fetch(`${RAW_URL}/logs/ci/latest.json?t=${Date.now()}`);
        if (!res.ok) throw new Error('Failed to fetch jobs');
        
        const data = await res.json();
        renderRealJobs(data.jobs || {});
    } catch (error) {
        console.error("CI Sync Error:", error);
        document.getElementById('jobsGrid').innerHTML = `<p class="text-danger">⚠️ Failed to sync live jobs from GitHub.</p>`;
    }
}

function renderRealJobs(jobsObject) {
    const grid = document.getElementById('jobsGrid');
    grid.innerHTML = '';
    
    // Convert object to array for mapping
    const jobs = Object.entries(jobsObject).map(([id, status]) => ({ id, name: formatJobName(id), status }));

    if (jobs.length === 0) {
        grid.innerHTML = `<p class="text-muted">No recent jobs found.</p>`;
        return;
    }

    jobs.forEach(job => {
        const isSuccess = job.status === 'success';
        const icon = isSuccess ? '✅' : (job.status === 'failure' ? '❌' : '⏭');
        const color = isSuccess ? 'var(--success)' : (job.status === 'failure' ? 'var(--danger)' : 'var(--text-muted)');
        
        grid.innerHTML += `
            <div class="job-card" onclick="openTerminal('${job.id}', '${job.status}')">
                <div>
                    <h4 style="font-size: 14px; margin-bottom: 4px;">${job.name}</h4>
                    <span style="font-size: 11px; color: var(--text-muted);">Status: ${job.status.toUpperCase()}</span>
                </div>
                <span class="job-status-icon" style="color: ${color}">${icon}</span>
            </div>
        `;
    });
}

function formatJobName(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// ════════════════════════════════════════════════════════════
// 4. TERMINAL MODAL (Live Log Fetching)
// ════════════════════════════════════════════════════════════
const terminalModal = document.getElementById('terminalModal');
const terminalTitle = document.getElementById('terminalTitle');
const terminalBody = document.getElementById('terminalBody');

async function openTerminal(jobId, status) {
    terminalTitle.innerText = `logs/${jobId}.log`;
    terminalModal.classList.remove('hidden');
    terminalBody.innerHTML = `<div class="t-line t-info">> [SYSTEM] Fetching raw logs for ${jobId}...</div>`;

    try {
        // We fetch the main markdown report as an example
        const res = await fetch(`${RAW_URL}/logs/ci/latest.md?t=${Date.now()}`);
        if (!res.ok) throw new Error('Log missing');
        const text = await res.text();
        
        // Simulating writing lines to terminal
        terminalBody.innerHTML = '';
        const lines = text.split('\n').slice(0, 30); // Show first 30 lines for speed
        lines.forEach(line => {
            if(line.trim() === '') return;
            const div = document.createElement('div');
            div.className = `t-line ${line.includes('Failed') || line.includes('Error') ? 't-error' : ''}`;
            div.innerText = `> ${line}`;
            terminalBody.appendChild(div);
        });
        terminalBody.scrollTop = terminalBody.scrollHeight;
    } catch (error) {
        terminalBody.innerHTML += `<div class="t-line t-error">> [ERROR] Could not retrieve logs. Run pipeline first.</div>`;
    }
}

function closeTerminal() { terminalModal.classList.add('hidden'); }

// ════════════════════════════════════════════════════════════
// 5. QUICK ACTIONS & GOD MODE (Backend API Calls)
// ════════════════════════════════════════════════════════════
async function triggerAction(actionType) {
    const confirmAction = confirm(`Execute critical action: ${actionType.toUpperCase()}?`);
    if(!confirmAction) return;

    try {
        const res = await fetch(`${API_BASE}/api/admin/actions/${actionType}`, { method: 'POST' });
        if(res.ok) alert(`✅ Action ${actionType} triggered successfully!`);
        else alert(`❌ Action failed with status: ${res.status}`);
    } catch (e) {
        alert(`❌ Network error while triggering ${actionType}.`);
    }
}

// God Mode Enforcer
document.getElementById('toggleAdminAuth').addEventListener('change', async (e) => {
    const isEnabled = e.target.checked;
    if (confirm(isEnabled ? "ENABLE global write access?" : "LOCK DOWN system (Read-Only Mode)?")) {
        try {
            const res = await fetch(`${API_BASE}/api/admin/rules`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: 'admin_authorized', value: isEnabled ? 'true' : 'false' })
            });
            if(!res.ok) throw new Error('Backend rejected rule change');
            console.log(`[SupremeAI] Rule 'admin_authorized' synced to: ${isEnabled}`);
        } catch (error) {
            alert('❌ Failed to update constitutional rule in god.py');
            e.target.checked = !isEnabled; // Revert switch
        }
    } else {
        e.target.checked = !isEnabled;
    }
});

// Auto-Refresh Binding
document.getElementById('btnRefresh').addEventListener('click', () => {
    fetchLiveJobs();
    document.querySelector('.sync-dot').style.animation = 'none';
    setTimeout(() => document.querySelector('.sync-dot').style.animation = 'pulse 2s infinite', 100);
});

// Init
fetchLiveJobs();
