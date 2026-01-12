function renderPrinterCard(p) {
    const dbStatus = p.PrinterStatus;
    const filamentPct = p.FilamentPct || 100;
    const innerDiameter = (filamentPct / 100) * 50;

    return `
    <div class="col-12 col-xl-6 mb-4">
        <div class="card h-100 shadow-sm printer-card-main">
            
            <div class="notch-container notch-top d-flex justify-content-between align-items-center">
                <h5 class="m-0 text-primary-custom">${p.PrinterName}</h5>
                <div class="d-flex align-items-center gap-3">
                    <span class="fs-4">${p.MaintenanceRequired === 1 ? '⚠️' : '✅'}</span>
                    <span class="badge bg-danger px-3 py-1">${dbStatus}</span>
                </div>
            </div>
            
            <div class="job-table-scroll-container">
                <table class="table table-sm mb-0 align-middle">
                    <thead class="sticky-top bg-light" style="font-size: 0.75rem; color: #1a237e;">
                        <tr>
                            <th style="width: 70px;" class="ps-3">POS</th>
                            <th>PARTNAME</th>
                            <th>TIME</th>
                            <th>MAT.</th>
                            <th>COLOR</th>
                            <th class="text-center">AKTION</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td class="ps-2">
                                <div class="d-flex align-items-center gap-2">
                                    <div class="d-flex flex-column">
                                        <span class="move-emoji" onclick="moveUp()">🔼</span>
                                        <span class="move-emoji" onclick="moveDown()">🔽</span>
                                    </div>
                                    <span class="fw-bold fs-5">1.</span>
                                </div>
                            </td>
                            <td class="small fw-bold">Gear_V2_Housing</td>
                            <td class="small text-muted">02:45h</td>
                            <td class="small text-muted">140g</td>
                            <td class="fw-bold small">BLACK</td>
                            <td class="text-center">
                                <div class="btn-group">
                                    <button class="btn btn-sm" style="background:#1a237e; color:white; font-size:0.65rem;">BOM</button>
                                    <button class="btn btn-sm btn-outline-danger" style="font-size:0.65rem;">✖</button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card-body p-4">
                <div class="row align-items-center mb-4 text-center">
                    <div class="col-4">
                        <div class="spool-outer" style="border-color: #bdbdbd;">
                            <div class="spool-inner" style="width: ${innerDiameter}px; height: ${innerDiameter}px; background: #1a237e;"></div>
                        </div>
                        <div class="mt-2">
                            <small class="d-block text-muted fw-bold">FILAMENT</small>
                            <span class="badge bg-dark p-1" style="font-size: 0.65rem;">PLA+ (Black)</span>
                        </div>
                    </div>

                    <div class="col-4">
                        <div class="d-flex justify-content-between mb-1 px-1" style="font-size: 0.8rem;">
                            <b class="text-accent-custom">65%</b>
                            <span class="text-muted">- 01:12h</span>
                        </div>
                        <div class="progress border mb-2" style="height: 12px; background: #bdbdbd;">
                            <div class="progress-bar" style="width: 65%; background-color: #0078a0;"></div>
                        </div>
                        <button class="btn halt-btn btn-sm w-100">DRUCKER STOPPEN</button>
                    </div>

                    <div class="col-4 border-start" style="border-color: #bdbdbd !important;">
                        <div class="small text-muted">STARTED: <b class="text-dark">08:30</b></div>
                        <div class="small text-muted mb-2">END: <b class="text-dark">14:20</b></div>
                        <i class="fas fa-check-double text-accent-custom fa-2x"></i>
                    </div>
                </div>

                <div class="notch-container notch-bottom mt-auto" style="border-color: #bdbdbd !important;">
                <div class="row text-center g-0 p-3" style="background-color: #1a237e; color: #f0f0f0;">
                    <div class="col-6 border-end" style="border-color: #bdbdbd !important;">
                        <small class="d-block fw-bold" style="color: #bdbdbd; font-size: 0.7rem;">DIMENSIONS</small>
                        <span class="fs-5 fw-bold text-white">${p.DimX}×${p.DimY}×${p.DimZ}</span>
                    </div>
                    <div class="col-6">
                        <small class="d-block fw-bold" style="color: #bdbdbd; font-size: 0.7rem;">NOZZLE</small>
                        <span class="fs-5 fw-bold text-white">0.40 mm</span>
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
        const response = await fetch('/admin/get_printers'); // Deine verifizierte Route
        if (!response.ok) throw new Error(`HTTP-Fehler! Status: ${response.status}`);
        
        // Hier wird 'printers' definiert
        const printers = await response.json(); 

        // Die Verarbeitung MUSS hier drin passieren
        if (printers && printers.length > 0) {
            container.innerHTML = printers.map(p => renderPrinterCard(p)).join('');
        } else {
            container.innerHTML = '<div class="col-12 text-center text-muted py-5">Keine Drucker in Datenbank gefunden.</div>';
        }

    } catch (err) {
        console.error("Dashboard Error:", err);
        container.innerHTML = `<div class="col-12 text-center text-danger py-5">Fehler beim Laden: ${err.message}</div>`;
    }
}

// Funktionen für die Buttons global verfügbar machen (wegen type="module")
window.managePrinter = function(id) { console.log("Wartung für:", id); };
window.editPrinter = function(id) { console.log("Edit für:", id); };

// Die Funktion muss auch aufgerufen werden!
document.addEventListener('DOMContentLoaded', () => {
    refreshPrinterDashboard();
});