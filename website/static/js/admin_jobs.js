document.addEventListener('DOMContentLoaded', () => {
    loadJobs('QUEUED');

    // Tab-Listener für Filterung
    document.querySelectorAll('#jobTabs .nav-link').forEach(tab => {
        tab.addEventListener('click', (e) => {
            // Aktiven Tab optisch umschalten
            document.querySelectorAll('#jobTabs .nav-link').forEach(t => t.classList.remove('active'));
            e.target.classList.add('active');
            
            const status = e.target.getAttribute('data-status');
            loadJobs(status);
        });
    });
});

function loadJobs(status) {
    const tableBody = document.getElementById('jobPoolBody');
    tableBody.innerHTML = '<tr><td colspan="8" class="text-center py-4"><i class="fas fa-cog fa-spin me-2"></i>Lade Daten...</td></tr>';

    fetch(`/admin/jobs/data?status=${status}`)
        .then(res => res.json())
        .then(jobs => {
            tableBody.innerHTML = '';
            if (jobs.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">Keine Jobs mit Status "${status}" gefunden.</td></tr>`;
                return;
            }

            jobs.forEach(job => {
                const row = `
                    <tr>
                        <td><span class="fw-mono small">${job.JobID}</span></td>
                        <td>
                            <div class="fw-bold">${job.PartName}</div>
                            <div class="small text-muted">${job.MaterialID} | ${job.Color}</div>
                        </td>
                        <td class="small text-muted">${job.SourceProjectID.substring(0,12)}...</td>
                        <td>
                            <span class="badge bg-light text-dark border">
                                <i class="fas fa-wrench me-1"></i>${job.NozzleDiam}mm
                            </span>
                        </td>
                        <td class="small">
                            <span class="text-muted">X:</span>${job.DimX} <span class="text-muted">Y:</span>${job.DimY} <span class="text-muted">Z:</span>${job.DimZ}
                        </td>
                        <td>${job.PrintTimeMin} Min</td>
                        <td>${renderStatusBadge(job.JobStatus)}</td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-outline-primary" onclick="assignToPrinter('${job.JobID}')">
                                <i class="fas fa-plus"></i>
                            </button>
                        </td>
                    </tr>
                `;
                tableBody.insertAdjacentHTML('beforeend', row);
            });
        });
}

function renderStatusBadge(status) {
    const mapping = {
        'QUEUED': 'bg-secondary',
        'PRINTING': 'bg-primary',
        'COMPLETED': 'bg-success',
        'FAILED': 'bg-danger'
    };
    return `<span class="badge ${mapping[status] || 'bg-dark'}">${status}</span>`;
}

/**
 * Aktualisiert die Ansicht basierend auf dem aktuell gewählten Tab-Status
 */
window.refreshJobPool = function() {
    // 1. Welcher Tab ist gerade offen?
    const activeTab = document.querySelector('#jobTabs .nav-link.active');
    const currentStatus = activeTab ? activeTab.getAttribute('data-status') : 'QUEUED';
    
    console.log(`Job-Pool Update getriggert. Lade Status: ${currentStatus}`);
    
    // 2. Bestehende loadJobs Funktion aufrufen (die den Fetch macht)
    if (typeof loadJobs === 'function') {
        loadJobs(currentStatus);
    } else {
        console.error("loadJobs nicht gefunden! Ist admin_jobs.js korrekt geladen?");
    }
};