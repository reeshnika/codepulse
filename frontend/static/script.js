// CodePulse Frontend Reports & Analytics Functions

async function downloadWeeklyReport() {
    window.open('/api/export/weekly.pdf', '_blank');
}

async function downloadSessionReport(sessionId) {
    window.open(`/api/export/${sessionId}.pdf`, '_blank');
}

async function showAnalytics() {
    try {
        const response = await fetch('/api/analytics/weekly');
        const data = await response.json();
        const panel = document.getElementById('analytics-panel');
        if (!panel) return;
        panel.style.display = 'block';
        panel.innerHTML = `
            <div class="analytics-card">
                <h4>Weekly Summary</h4>
                <p>Total Sessions: ${data.sessions_count}</p>
                <p>Total Duration: ${Math.round(data.total_duration / 60)} minutes</p>
                <p>Average Flow Score: ${data.avg_flow_score.toFixed(1)}</p>
                <p>Best Day: ${data.best_day}</p>
            </div>
        `;
    } catch (err) {
        console.error('Error fetching analytics:', err);
    }
}

async function clearAllSessions() {
    if (confirm('Delete all session history? This cannot be undone.')) {
        try {
            const response = await fetch('/api/clear-sessions', { method: 'POST' });
            const result = await response.json();
            alert(`Cleared ${result.deleted || 0} session(s).`);
            if (typeof fetchSessions === 'function') {
                fetchSessions();
            }
        } catch (error) {
            console.error('Error clearing sessions:', error);
            alert('Failed to clear sessions.');
        }
    }
}

function getStateClass(state) {
    if (state === 'NOT_CODE') return 'not-code';
    if (state === 'FLOW STATE' || state === 'FLOW_STATE') return 'flow';
    if (state === 'PRODUCTIVE') return 'productive';
    if (state === 'WORKING') return 'working';
    if (state === 'STRUGGLING') return 'struggling';
    if (state === 'BLOCKED') return 'blocked';
    return 'idle';
}

