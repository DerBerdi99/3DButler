function renderPrinterCard(p) {
    const dbStatus = p.PrinterStatus;
    const filamentPct = p.FilamentPct || 100;
    const innerDiameter = (filamentPct / 100) * 50;

    return `
    <div class="printer-card-wrapper" 
         data-printer-id="${p.PrinterID}"
         ondragover="event.preventDefault(); this.classList.add('printer-drag-hover');"
         ondragleave="this.classList.remove('printer-drag-hover');"
         ondrop="if(typeof window.handleJobDrop === 'function') { window.handleJobDrop(event, '${p.PrinterID}'); } else { event.preventDefault(); }"> 
        
        <div class="card shadow-sm printer-card-main">
            <div class="notch-container notch-top d-flex justify-content-between align-items-center">
                <h5 class="m-0 text-primary-custom">${p.PrinterName}</h5>
                <div class="d-flex align-items-center gap-3">
                    <span class="fs-4">${p.MaintenanceRequired === 1 ? '⚠️' : '✅'}</span>
                    <span class="badge bg-danger px-3 py-1">${dbStatus}</span>
                </div>
            </div>
            
            <div class="job-table-scroll-container" style="max-height: 200px; overflow-y: auto;">
                <table class="table table-sm mb-0 align-middle">
                    <thead class="sticky-top bg-light" style="font-size: 0.75rem; color: #1a237e;">
                        <tr>
                            <th style="width: 70px;" class="ps-3">POS</th>
                            <th>PARTNAME</th>
                            <th>TIME</th>
                            <th class="text-center">AKTION</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${p.jobs && p.jobs.length > 0 ? p.jobs.map((job, index) => `
                            <tr>
                                <td class="ps-2">
                                    <span class="fw-bold fs-5">${index + 1}.</span>
                                </td>
                                <td class="small fw-bold text-truncate" style="max-width: 130px;" title="${job.PartName}">
                                    ${job.PartName}
                                </td>
                                <td class="small text-muted">${job.PrintTimeMin} Min</td>
                                <td class="text-center">
                                    <button class="btn btn-sm btn-outline-danger" 
                                            onclick="removeJobFromPrinter('${job.QueueID}', '${p.PrinterID}')">
                                        ✖
                                    </button>
                                </td>
                            </tr>
                        `).join('') : `
                            <tr>
                                <td colspan="4" class="text-center text-muted small py-4">
                                    <i class="fas fa-inbox d-block mb-1 fs-5 opacity-50"></i>Keine Jobs eingereiht
                                </td>
                            </tr>
                        `}
                    </tbody>
                </table>
            </div>

            <div class="card-body p-3">
                <div class="row align-items-center text-center g-2">
                    <div class="col-4">
                        <div class="spool-outer mx-auto">
                            <div class="spool-inner" style="width:${innerDiameter}px; height:${innerDiameter}px;"></div>
                        </div>
                        <small class="d-block text-muted mt-1">PLA+ (Black)</small>
                    </div>
                    <div class="col-8">
                        <div class="progress mb-2" style="height: 12px;">
                            <div class="progress-bar" style="width: 65%;"></div>
                        </div>
                        <button class="btn btn-danger btn-sm w-100" style="font-size:0.7rem;">STOPPEN</button>
                    </div>
                </div>
            </div>

            <div class="notch-container notch-bottom mt-auto">
                <div class="row text-center g-0 p-2" style="background-color: #1a237e; color: #fff;">
                    <div class="col-6 border-end border-secondary">
                        <small class="d-block text-white-50" style="font-size: 0.6rem;">DIMENSIONS</small>
                        <span class="fw-bold">${p.DimX}×${p.DimY}×${p.DimZ}</span>
                    </div>
                    <div class="col-6">
                        <small class="d-block text-white-50" style="font-size: 0.6rem;">NOZZLE</small>
                        <span class="fw-bold">0.40 mm</span>
                    </div>
                </div>
            </div>
        </div>
    </div>`;
}

// Funktion zum Aktualisieren des Drucker-Dashboards

async function refreshPrinterDashboard() {
    const container = document.getElementById('printer_grid_container');
    if (!container) return;

    try {
        const response = await fetch('/admin/get_printers');
        if (!response.ok) throw new Error(`Server-Fehler: ${response.status}`);
        
        const printers = await response.json(); 
        console.log("Drucker Daten:", printers); // PRÜFUNG IN DER KONSOLE (F12)

        if (printers && printers.length > 0) {
            // Dies löscht den Spinner und setzt die Karten nebeneinander
            container.innerHTML = printers.map(p => renderPrinterCard(p)).join('');
        } else {
            container.innerHTML = '<div class="text-white p-5">Keine Drucker in der Datenbank.</div>';
        }

    } catch (err) {
        console.error("Dashboard Error:", err);
        container.innerHTML = `<div class="text-danger p-5">Fehler: ${err.message}</div>`;
    }
}

// Funktionen für die Buttons global verfügbar machen (wegen type="module")
window.managePrinter = function(id) { console.log("Wartung für:", id); };
window.editPrinter = function(id) { console.log("Edit für:", id); };
window.handleJobDrop = function(e, printerId) {
    e.preventDefault();
    
    // Visuellen Hover-Effekt entfernen
    const wrapper = document.querySelector(`[data-printer-id="${printerId}"]`);
    if (wrapper) wrapper.classList.remove('printer-drag-hover');

    // JobID aus dem Datentransfer holen
    const jobId = e.dataTransfer.getData('text/plain');
    if (!jobId) return;

    // API-Request an das Flask-Backend
    fetch('/admin/assign_job_to_printer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            job_id: jobId,
            printer_id: printerId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Live-Aktualisierung beider Ansichten (Job-Pool und Drucker-Grid)
            if (typeof window.loadJobs === 'function') {
                // Lädt die Warteschlange neu (wir gehen vom Status QUEUED aus)
                window.loadJobs('QUEUED'); 
            }
            if (typeof refreshPrinterDashboard === 'function') {
                refreshPrinterDashboard();
            }
        } else {
            console.error("Zuweisungsfehler vom Server:", data.message);
            alert("Fehler: " + data.message);
        }
    })
    .catch(err => console.error("Netzwerkfehler beim Drop-Event:", err));
};

window.removeJobFromPrinter = function(queueId, printerId) {
    if (!confirm("Möchtest du diesen Job wirklich aus der Warteschlange des Druckers entfernen?")) return;

    fetch('/admin/remove_job_from_printer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            queue_id: queueId,
            printer_id: printerId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (typeof window.loadJobs === 'function') window.loadJobs('QUEUED');
            if (typeof refreshPrinterDashboard === 'function') {
                refreshPrinterDashboard();
            }
        } else {
            alert("Fehler beim Entfernen: " + data.message);
        }
    })
    .catch(err => console.error("Netzwerkfehler beim Entfernen des Jobs:", err));
};

document.addEventListener('DOMContentLoaded', () => {
    refreshPrinterDashboard();
});