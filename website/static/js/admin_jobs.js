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
                // 1. Element als echtes TR-Objekt erstellen statt als reinen HTML-String
                const row = document.createElement('tr');
                
                // === DRAG & DROP EIGENSCHAFTEN AN HÄNGEN ===
                row.setAttribute('draggable', 'true');
                row.style.cursor = 'grab'; // Zeigt die "Hand" beim Drüberfahren

                // Event-Listener beim Start des Ziehens
                row.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('text/plain', job.JobID);
                    row.classList.add('opacity-50'); // Visuelles Feedback
                    
                    // Erlaubt das Kopieren/Verschieben
                    e.dataTransfer.effectAllowed = 'move'; 
                });

                // Event-Listener wenn das Ziehen beendet wird
                row.addEventListener('dragend', () => {
                    row.classList.remove('opacity-50');
                });

                // 2. Den inneren HTML-Inhalt wie gewohnt befüllen
                row.innerHTML = `
                    <td><span class="fw-mono small" title="${job.JobID}">${job.JobID.substring(0, 12)}</span></td>
                    <td>
                        <div class="fw-bold">${job.PartName}</div>
                        <div class="small text-muted" title="${job.MaterialID}">${job.MaterialID.substring(0, 12) || 'null'} | ${job.Color}</div>
                    </td>
                    <td><span class="fw-mono small" title="${job.FileID}">${job.FileID.substring(0, 12)}</span></td>
                    <td><span class="fw-mono small" title="${job.FileName}">${job.FileName}</span></td>

                    <td class="small text-muted" title="${job.SourceProjectID}">${job.SourceProjectID.substring(0,12)}...</td>
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
                `;

                // 3. Das fertig konfigurierte Objekt an die Tabelle anhängen
                tableBody.appendChild(row);
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