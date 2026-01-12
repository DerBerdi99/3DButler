// admin_blueprints.js - Vollständige, strukturierte Fassung

// 0. DATEN-INITIALISIERUNG
const materialsData = JSON.parse(document.getElementById('inventory-data').textContent || '[]');
const profilesData = JSON.parse(document.getElementById('profiles-data').textContent || '[]');
// Globale Verfügbarkeit der Material/Profil-Daten im Fensterobjekt
window.inventoryMaterials = materialsData;
window.printProfiles = profilesData;

// --- HILFSFUNKTIONEN (TEMPLATES & LOGIK) ---
/**
 * RENDER-LOGIK & DATEN-BINDUNG
 * -------------------------------------------------------------------------
 * Das Template nutzt Snake_Case (dim_x, part_name), um konsistent mit dem JSON-Backend zu bleiben.
 * Fallbacks (||) sichern die Kompatibilität zwischen neu erstellten Zeilen und DB-Daten.
 */

// Erzeugt das HTML für eine Bauteil-Zeile. 
// Verarbeitet sowohl DB-Objekte (part_name) als auch Initial-Objekte (name).
function renderPartTemplate(data = {}, uniqueId) {

    const isBought = (data.process === 'BOUGHT');
    const colors = ['BLACK', 'WHITE', 'GRAY', 'RED', 'BLUE', 'GREEN'];
    return `
    <div class="bom-part-row bg-dark border border-secondary p-2 mb-2 rounded shadow-sm ${isBought ? 'is-bought' : ''}" 
        style="border-left: 5px solid ${isBought ? '#ffc107' : '#0dcaf0'}">
        <div class="bom-part-item d-flex flex-wrap align-items-end gap-2">
            
            <div style="flex: 2; min-width: 180px;">
                <label class="text-info fw-bold small mb-1">Bezeichnung</label>
                <input type="text" class="form-control form-control-sm part-name text-white bg-dark border-secondary" 
                       placeholder="Bauteil..." value="${data.part_name || ''}">
            </div>

            <div style="width: 60px;">
                <label class="text-info fw-bold small mb-1">Menge</label>
                <input type="number" class="form-control form-control-sm part-qty text-white bg-dark border-secondary" 
                       value="${data.quantity || 1}" min="1">
            </div>

            <div style="width: 110px;">
                <label class="text-info fw-bold small mb-1">Verfahren</label>
                <select class="form-select form-select-sm part-process bg-dark text-white border-secondary">
                    <option value="FDM_PRINT" ${data.process === 'FDM_PRINT' ? 'selected' : ''}>FDM</option>
                    <option value="CNC" ${data.process === 'CNC' ? 'selected' : ''}>CNC</option>
                    <option value="BOUGHT" ${data.process === 'BOUGHT' ? 'selected' : ''}>Kaufteil</option>
                </select>
            </div>

            <div class="d-flex gap-1 border border-secondary rounded p-1" style="background: rgba(255,255,255,0.05)">
                <div style="width: 50px;">
                    <label class="text-warning small mb-1" style="font-size: 0.65rem;">X (mm)</label>
                    <input type="number" min="0" step="1" class="form-control form-control-sm part-dim-x bg-dark text-white border-0 p-0 text-center" value="${data.dim_x || 0}">
                </div>
                <div style="width: 50px;">
                    <label class="text-warning small mb-1" style="font-size: 0.65rem;">Y (mm)</label>
                    <input type="number" min="0" step="1" class="form-control form-control-sm part-dim-y bg-dark text-white border-0 p-0 text-center" value="${data.dim_y || 0}">
                </div>
                <div style="width: 50px;">
                    <label class="text-warning small mb-1" style="font-size: 0.65rem;">Z (mm)</label>
                    <input type="number" min="0" step="1" class="form-control form-control-sm part-dim-z bg-dark text-white border-0 p-0 text-center" value="${data.dim_z || 0}">
                </div>
            </div>

            <div style="width: 110px;">
                <label class="text-secondary small mb-1">Material</label>
                <select class="form-select form-select-sm part-material bg-dark text-white border-secondary">
                    ${(window.inventoryMaterials || []).map(m => `<option value="${m.MaterialID}" ${data.materialId == m.MaterialID ? 'selected' : ''}>${m.MaterialName}</option>`).join('')}
                </select>
            </div>

            <div style="width: 100px;">
                <label class="text-secondary small mb-1">Farbe</label>
                <select class="form-select form-select-sm part-color bg-dark text-white border-secondary">
                    ${colors.map(c => `<option value="${c}" ${data.color === c ? 'selected' : ''}>${c}</option>`).join('')}
                </select>
            </div>

            <div style="width: 100px;">
                <label class="text-secondary small mb-1">Profil</label>
                <select class="form-select form-select-sm part-profile bg-dark text-white border-secondary">
                    ${(window.printProfiles || []).map(p => `<option value="${p.ProfileID}" ${data.profileId == p.ProfileID ? 'selected' : ''}>${p.ProfileName}</option>`).join('')}
                </select>
            </div>

            <div style="width: 70px;">
                <label class="text-secondary small mb-1">Nozzle</label>
                <select class="form-select form-select-sm part-nozzle bg-dark text-white border-secondary">
                    <option value="0.4" ${data.nozzle == '0.4' ? 'selected' : ''}>0.4</option>
                    <option value="0.2" ${data.nozzle == '0.2' ? 'selected' : ''}>0.2</option>
                    <option value="0.6" ${data.nozzle == '0.6' ? 'selected' : ''}>0.6</option>
                    <option value="0.8" ${data.nozzle == '0.8' ? 'selected' : ''}>0.8</option>
                </select>
            </div>

            <div style="width: 70px;">
                <label class="text-secondary small mb-1">Gewicht(g)</label>
                <input type="number" min="0" step="0.1" class="form-control form-control-sm part-weight bg-dark text-white border-secondary" value="${data.weight || 0.0}">
            </div>

            <div style="width: 65px;">
                <label class="text-secondary small mb-1">Zeit(min)</label>
                <input type="number" min="0" class="form-control form-control-sm part-time bg-dark text-white border-secondary" value="${data.print_time || 0}">
            </div>

            <div class="ms-auto">
                <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="removePartRow(this)">
                    &#x2715;
                </button>
            </div>
        </div>
    </div>`;
}

/**
 * DATEN-EXTRAKTION (BACKEND-INTERFACE)
 * -------------------------------------------------------------------------
 * Sammelt alle Werte aus dem DOM und konvertiert sie in korrekte Datentypen.
 * WICHTIG: Erzeugt das 'is_bought' Flag für Abwärtskompatibilität im Backend.
 */
function extractPartData(row) {
    const processVal = row.querySelector('.part-process').value;
    return {
        part_name: row.querySelector('.part-name').value.trim(),
        quantity: parseInt(row.querySelector('.part-qty').value) || 1,
        process: processVal,
        material_id: row.querySelector('.part-material').value,
        color: row.querySelector('.part-color').value,
        profile_id: row.querySelector('.part-profile').value,
        weight: parseFloat(row.querySelector('.part-weight').value) || 0,
        print_time: parseInt(row.querySelector('.part-time').value) || 0,
        // Dimensionen mappen (neu für Backend)
        dim_x: parseInt(row.querySelector('.part-dim-x').value) || 0,
        dim_y: parseInt(row.querySelector('.part-dim-y').value) || 0,
        dim_z: parseInt(row.querySelector('.part-dim-z').value) || 0,
        nozzle: row.querySelector('.part-nozzle').value,
        // Mapping für Abwärtskompatibilität im Backend
        is_bought: (processVal === 'BOUGHT')
    };
}

// Registriert alle Event-Listener für eine neue Zeile.
// Steuert die Deaktivierung von Feldern, wenn das Verfahren auf 'BOUGHT' steht.
function bindPartEvents(row) {
    const processSelect = row.querySelector('.part-process');
    // Die Felder, die bei Kaufteilen gesperrt werden
    const inputs = row.querySelectorAll('.part-material, .part-color, .part-profile, .part-weight, .part-time, .part-dim-x, .part-dim-y, .part-dim-z, .part-nozzle');

    processSelect.addEventListener('change', function() {
        const isBought = (this.value === 'BOUGHT');
        row.classList.toggle('opacity-50', isBought);
        row.style.borderLeft = isBought ? "5px solid #ffc107" : "5px solid #0dcaf0";
        
        inputs.forEach(i => {
            i.disabled = isBought;
            if (isBought && i.tagName !== 'SELECT') i.value = ''; 
        });
        updateBOMStats();
    });

    // Live-Update für Statistik
    row.querySelectorAll('.part-qty, .part-time').forEach(el => {
        el.addEventListener('input', updateBOMStats);
    });
}

/**
 * BERECHNUNG & STATISTIK
 * -------------------------------------------------------------------------
 * Summiert Mengen und Zeiten. Kaufteile werden in der Zeitberechnung ignoriert.
 * Sicherheitsabfragen verhindern Abstürze bei fehlenden DOM-Elementen.
 */
function updateBOMStats() {
    let totalQty = 0;
    let totalTime = 0;
    let boughtCount = 0;
    let totalItems = 0;

    document.querySelectorAll('.bom-part-row').forEach(row => {
        const qty = parseInt(row.querySelector('.part-qty').value) || 0;
        const time = parseInt(row.querySelector('.part-time').value) || 0;
        // Check via Dropdown statt Checkbox
        const isBought = (row.querySelector('.part-process').value === 'BOUGHT');

        totalQty += qty;
        totalItems++;
        if (isBought) {
            boughtCount++;
        } else {
            totalTime += (time * qty);
        }
    });

    if(document.getElementById('stats_total_parts')) document.getElementById('stats_total_parts').textContent = totalQty;
    if(document.getElementById('stats_total_time')) document.getElementById('stats_total_time').textContent = `${totalTime} min (${(totalTime/60).toFixed(1)}h)`;
    
    const ratio = totalItems > 0 ? Math.round((boughtCount / totalItems) * 100) : 0;
    if(document.getElementById('stats_bought_ratio')) document.getElementById('stats_bought_ratio').textContent = `${ratio}%`;
}

/**
 * WORKBENCH-LIFECYCLE
 * -------------------------------------------------------------------------
 * openBOMWorkbench: Lädt JSON, räumt Container und rendert via Template.
 * fillRowData: Fungiert als Post-Processing-Hook nach dem Einfügen ins DOM.
 * Da das Template die Werte bereits setzt, triggert diese Funktion nur noch 
 * die reaktive Logik (bindPartEvents & Change-Events).
 */
function fillRowData(row, data) {
    // 1. Das Verfahren wird bereits durch das Template korrekt im HTML gesetzt.
    // Wir müssen nur sicherstellen, dass bindPartEvents die Logik anhängt.
    bindPartEvents(row);
    
    // 2. Den visuellen Status (Ausgrauen/Farbe) basierend auf dem geladenen Wert triggern.
    const processSelect = row.querySelector('.part-process');
    if (processSelect) {
        processSelect.dispatchEvent(new Event('change'));
    }
}

// Entfernt eine Bauteil-Zeile und aktualisiert die Statistik.
function removePartRow(btn) {
    btn.closest('.bom-part-row').remove();
    updateBOMStats(); // Statistik nach dem Löschen aktualisieren
}

// --- CORE FUNKTIONEN ---
// Öffnet den Manufacturing Viewer und füllt die Felder.
function openManufacturingViewer(button) {
    const bpId = button.dataset.blueprintId;
    const form = document.getElementById('viewerForm');
    if (!form) return;
    // Setzt die Aktions-URL und füllt die Felder
    form.action = form.dataset.baseUrl + bpId;
    document.getElementById('view_project_id').value = button.dataset.projectId || '';
    document.getElementById('view_project_name').textContent = button.dataset.projectName || 'Unbekannt';
    document.getElementById('view_volume').value = button.dataset.volume || '';
    document.getElementById('view_weight').value = button.dataset.weight || '';
    document.getElementById('view_print_time').value = button.dataset.time || '';
    document.getElementById('view_profile_id').value = button.dataset.profile || '';
    document.getElementById('view_material_id').value = button.dataset.material || '';

    new bootstrap.Offcanvas(document.getElementById('manufacturingViewer')).show();
}
// Öffnet die BOM-Workbench und lädt die Daten via Fetch.
async function openBOMWorkbench(button) {
    const bpId = button.dataset.projectId;
    const container = document.getElementById('bom_parts_container');
    container.innerHTML = ''; 
    
    document.getElementById('bom_proj_id_display').textContent = bpId;
    document.getElementById('bom_proj_name').textContent = button.dataset.projectName;
    // Fetch der BOM-Daten
    try {
        const response = await fetch(`/admin/get_bom/${bpId}`);
        const result = await response.json();
        // Verarbeiten der geladenen Daten
        if (result.success && result.data) {
            const data = result.data;
            // Baugruppen rendern
            if (data.assemblies) {
                data.assemblies.forEach(asm => {
                    const assemblyId = `asm_${Math.random().toString(36).slice(2, 7)}`;
                    createAssemblyContainer(asm.assembly_name, assemblyId);
                    const asmPartsContainer = document.querySelector(`#${assemblyId} .parts-container`);
                    // Teile der Baugruppe rendern
                    if (asm.parts) {
                        asm.parts.forEach(part => {
                            const uniqueId = `part_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`;
                            // Hier das ganze part-Objekt übergeben!
                            asmPartsContainer.insertAdjacentHTML('beforeend', renderPartTemplate(part, uniqueId));
                            fillRowData(asmPartsContainer.lastElementChild, part);
                        });
                    }
                });
            }

            if (data.loose_parts) {
                data.loose_parts.forEach(part => {
                    // Hier ebenfalls das ganze Objekt nutzen
                    const uniqueId = `part_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`;
                    container.insertAdjacentHTML('beforeend', renderPartTemplate(part, uniqueId));
                    fillRowData(container.lastElementChild, part);
                });
            }
        }
    } catch (e) {
        console.error("Fehler beim Laden der BOM:", e);
    }

    new bootstrap.Modal(document.getElementById('bomWorkbench')).show();
    updateBOMStats();
}
// Fügt ein neues Bauteil im DOM hinzu.
function addNewPart(data = {}) {
    const container = document.getElementById('bom_parts_container');
    const uniqueId = `part_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    
    container.insertAdjacentHTML('beforeend', renderPartTemplate(data, uniqueId));
    
    const newRow = container.lastElementChild;
    bindPartEvents(newRow);
    updateBOMStats(); // <--- NEU: Direkt beim Erstellen rechnen
}
// Erstellt eine neue Baugruppen-Container im DOM.
// Optionaler Parameter 'forcedId' für spezifische IDs (z.B. beim Laden).
function createAssemblyContainer(name = "Neue Baugruppe", forcedId = null) {
    const container = document.getElementById('bom_parts_container');
    const assemblyId = forcedId || `asm_${Math.random().toString(36).slice(2, 7)}`;
    const asmHtml = `
        <div class="assembly-group border border-info p-3 mb-4 rounded bg-dark shadow-sm" id="${assemblyId}">
            <div class="d-flex justify-content-between align-items-center mb-3 border-bottom border-info pb-2">
                <input type="text" class="form-control form-control-sm bg-transparent text-info fw-bold border-0 w-50 asm-title" value="${name}">
                <div class="btn-group">
                    <button type="button" class="btn btn-sm btn-outline-info" onclick="addNewPartToAssembly('${assemblyId}')">+ Part</button>
                    <button type="button" class="btn btn-sm btn-outline-danger ms-2" onclick="this.closest('.assembly-group').remove()">&#x2715;</button>
                </div>
            </div>
            <div class="parts-container"></div>
        </div>`;
    container.insertAdjacentHTML('beforeend', asmHtml);
}

// Flash-Nachrichtenanzeige für successmessages links, mitte und rechts des hauptcontaiers

window.showBOMSaveFlash = function(message, category = 'success') {
    const slot = document.getElementById('flash-container-center');
    if (!slot) return;

    slot.innerHTML = `
        <div class="alert alert-${category} alert-dismissible fade show shadow" role="alert">
            <i class="fas fa-save me-2"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
};

window.showJobProductionFlash = function(message, category = 'success') {
    const slot = document.getElementById('flash-container-left');
    if (!slot) return;

    slot.innerHTML = `
        <div class="alert alert-${category} alert-dismissible fade show shadow-sm" role="alert">
            <i class="fas fa-industry me-2"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
};

window.showJobAssignmentFlash = function(message, category = 'success') {
    const slot = document.getElementById('flash-container-right');
    if (!slot) return;

    slot.innerHTML = `
        <div class="alert alert-${category} alert-dismissible fade show shadow-sm" role="alert">
            <i class="fas fa-industry me-2"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
};
/**
 * SPEICHER-LOGIK
 * -------------------------------------------------------------------------
 * Iteriert durch Baugruppen (Assemblies) und lose Teile.
 * Filtert leere Zeilen ohne Bezeichnung aus, um die DB sauber zu halten.
 */
function saveFullBOM() {
    const bpId = document.getElementById('bom_proj_id_display').textContent.trim();
    if (!bpId) return alert("Keine Projekt-ID!");

    // Daten sammeln
    const assemblies = [];
    document.querySelectorAll('.assembly-group').forEach(asm => {
        const parts = [];
        asm.querySelectorAll('.bom-part-row').forEach(row => {
            const d = extractPartData(row);
            if (d.part_name) parts.push(d);
        });
        assemblies.push({ 
            assembly_name: asm.querySelector('.asm-title').value, 
            parts: parts 
        });
    });

    const looseParts = [];
    document.querySelectorAll('#bom_parts_container > .bom-part-row').forEach(row => {
        const d = extractPartData(row);
        if (d.part_name) looseParts.push(d);
    });

    const payload = { assemblies: assemblies, loose_parts: looseParts };

    fetch(`/admin/save_bom/${bpId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(response => {
        if (!response.ok) throw new Error(`Server-Status: ${response.status}`);
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // 1. Feedback: BOM wurde gesichert
            console.log("Server Antwort:", data);
            if (window.showBOMSaveFlash) {
                showBOMSaveFlash("Stückliste aktualisiert", "success");
            }

            // 2. Modal schließen (Wichtig!)
            const bomModalEl = document.getElementById('bomWorkbench');
            if (bomModalEl) {
                const modalInstance = bootstrap.Modal.getInstance(bomModalEl);
                if (modalInstance) modalInstance.hide();
            }

            // HINWEIS: refreshJobPool() und Counter-Inkrement 
            // fliegen hier raus, da sie hier nichts zu suchen haben!
        } else {
            if (window.showBOMSaveFlash) {
                showBOMSaveFlash("Fehler beim Speichern: " + data.message, "danger");
            }
        }
    })
    .catch(err => {
        console.error("Kritischer Fehler:", err);
        if (window.showBOMSaveFlash) {
            showBOMSaveFlash("Netzwerkfehler: " + err.message, "danger");
        }
    });
}

// --- MODAL RESIZER & DRAGGER ---
// Ermöglicht das Ziehen und Größenändern des Modals
function initModalResizerAndDragger(modalId) {
    const modal = document.getElementById(modalId);
    const dialog = modal.querySelector('.modal-dialog');
    const header = modal.querySelector('.modal-header');
    
    // Resize Handle hinzufügen
    const handle = document.createElement('div');
    handle.className = 'resize-handle-e';
    dialog.querySelector('.modal-content').appendChild(handle);

    // --- DRAG LOGIK ---
    let isDragging = false;
    let dragOffset = { x: 0, y: 0 };

    header.addEventListener('mousedown', (e) => {
        if (e.target.closest('button') || e.target.closest('input')) return;
        isDragging = true;
        dragOffset.x = e.clientX - dialog.offsetLeft;
        dragOffset.y = e.clientY - dialog.offsetTop;
        header.style.cursor = 'grabbing';
    });

    // --- RESIZE LOGIK ---
    let isResizing = false;
    let startWidth = 0;
    let startX = 0;
    // Resize Handle Mousedown
    handle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = dialog.offsetWidth;
        document.body.style.cursor = 'e-resize';
        e.preventDefault();
    });

    // Zentraler MouseMove für beides
    document.addEventListener('mousemove', (e) => {
        if (isDragging) {
            dialog.style.margin = '0';
            dialog.style.position = 'absolute';
            dialog.style.left = (e.clientX - dragOffset.x) + 'px';
            dialog.style.top = (e.clientY - dragOffset.y) + 'px';
        }

        if (isResizing) {
            const newWidth = startWidth + (e.clientX - startX);
            if (newWidth > 500) { // Min-Width Check
                dialog.style.width = newWidth + 'px';
                dialog.style.maxWidth = 'none'; // Bootstrap Override
            }
        }
    });

    // MouseUp zum Stoppen von Drag & Resize
    document.addEventListener('mouseup', () => {
        isDragging = false;
        isResizing = false;
        header.style.cursor = 'move';
        document.body.style.cursor = 'default';
    });
}

// --- JOB TRIGGERING FUNCTIONALITY ---
// Triggern der Produktionsvorbereitung via Fetch API
window.triggerProduction = function triggerProduction(projectId) {
    const btn = document.getElementById(`trigger-btn-${projectId}`);
    const signal = document.getElementById(`job-signal-${projectId}`);
    if (!btn) return;

    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-cog fa-spin"></i> PREPROCESSING...';
    btn.classList.add('opacity-50');
    btn.disabled = true;

    fetch(`/admin/generate_jobs/${projectId}`, { method: 'POST' })
    .then(response => {
        if (!response.ok) throw new Error('Netzwerk-Fehler oder Server-Fehler (500)');
        return response.json();
    })
    .then(data => {
        // UI Button sofort zurücksetzen
        btn.innerHTML = originalContent;
        btn.classList.remove('opacity-50');
        btn.disabled = false;

        if (data.success) {
            // 1. Nachricht anzeigen (Prüfung ob Funktion existiert)
            if (typeof showJobProductionFlash === 'function') {
                showJobProductionFlash(data.message || "Jobs erfolgreich hinzugefügt", "success");
            }

            // 2. Pool aktualisieren
            if (window.refreshJobPool) {
                window.refreshJobPool();
            }

            // 3. Lokale Animation auf der Card
            if (signal) {
                signal.style.display = 'block';
                signal.style.opacity = '1';
                setTimeout(() => {
                    signal.style.transition = "opacity 1s ease";
                    signal.style.opacity = "0";
                    setTimeout(() => { signal.style.display = 'none'; }, 1000);
                }, 3000);
            }
        } else {
            // Server hat geantwortet, aber Erfolg war False
            if (typeof showJobProductionFlash === 'function') {
                showJobProductionFlash(data.message || "Fehler beim Erzeugen", "danger");
            }
        }
    })
    .catch(err => {
        console.error("Fehler:", err);
        btn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> FEHLER';
        btn.classList.add('bg-danger');
        btn.disabled = false;
        if (typeof showJobProductionFlash === 'function') {
            showJobProductionFlash("Kritischer Fehler: " + err.message, "danger");
        }
    });
};

// Fügt ein neues Bauteil zu einer bestehenden Baugruppe hinzu.
window.addNewPartToAssembly = function(assemblyId) {
    const container = document.querySelector(`#${assemblyId} .parts-container`);
    const uniqueId = `part_asm_${Date.now()}`;
    
    container.insertAdjacentHTML('beforeend', renderPartTemplate({}, uniqueId));
    
    const newRow = container.lastElementChild;
    bindPartEvents(newRow);
    updateBOMStats(); // <--- NEU: Direkt beim Erstellen rechnen
};

// --- INITIALISIERUNG ---
// Initialisiert den Modal Resizer und Dragger sowie globale Event-Listener.

document.addEventListener('DOMContentLoaded', () => {
    initModalResizerAndDragger('bomWorkbench');
    const myModalEl = document.getElementById('bomWorkbench');
    myModalEl.addEventListener('shown.bs.modal', function () {
        document.removeEventListener('focusin', bootstrap.Modal.prototype._enforceFocus);
    });
    // Globales Löschen für Blueprints
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.delete-btn');
        if (btn && confirm(`Blueprint wirklich löschen?`)) {
            const form = document.createElement('form');
            form.method = 'POST'; form.action = btn.dataset.deleteUrl;
            document.body.appendChild(form); form.submit();
        }
    });
});
// Entfernt eine Bauteil-Zeile und aktualisiert die Statistik.
window.removePartRow = function(btn) {
    const row = btn.closest('.bom-part-row');
    if (row) {
        row.remove();
        updateBOMStats(); // Wichtig: Statistik neu berechnen
    }
};



// Exports
window.openManufacturingViewer = openManufacturingViewer;
window.openBOMWorkbench = openBOMWorkbench;
window.addNewPart = addNewPart;
window.createAssemblyContainer = createAssemblyContainer;
window.saveFullBOM = saveFullBOM;
window.updateBOMStats = updateBOMStats;