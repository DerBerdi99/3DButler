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
    
    const fileId = data.file_id || data.fileId || "";
    const fileName = data.file_name || data.fileName || "";
    
    const hasFile = !!fileId;
    const fileLabel = hasFile ? fileName : 'Keine Datei';
    const textClass = hasFile ? 'text-success fw-bold' : 'text-danger italic';

    return `
    <div class="bom-part-row bg-dark border border-secondary p-2 mb-2 rounded shadow-sm ${isBought ? 'is-bought' : ''}" 
        id="${uniqueId || 'part_' + Math.random().toString(36).slice(2, 7)}"
        style="border-left: 5px solid ${isBought ? '#ffc107' : '#0dcaf0'}">
        <div class="bom-part-item d-flex flex-wrap align-items-end gap-2">
            
            <div class="part-file-dropzone border border-dashed border-secondary rounded p-1 text-center bg-black bg-opacity-25" 
                 style="width: 160px; height: 31px; display: flex; align-items: center; justify-content: center; overflow: hidden; cursor: default; transition: all 0.2s;">
                
                <input type="hidden" class="part-file-id" value="${data.file_id || ''}">
                
                <div class="part-file-name-display ${textClass} text-truncate px-1" style="font-size: 0.9rem; font-weight: bold;" title="${data.file_name || ''}">
                    <i class="fa-solid ${hasFile ? 'fa-file-circle-check text-success' : 'fa-file-import text-muted'} me-1"></i>
                    ${fileLabel}
                </div>
            </div>
            
            <div style="flex: 2; min-width: 140px;">
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
/**
 * Hilfsfunktion: Extrahiert alle Formulardaten aus einer Bauteil-Zeile.
 * @param {HTMLElement} row - Die .bom-part-row
 * @returns {Object} Das extrahierte Bauteil-Datenobjekt
 */
function extractPartData(row) {
    // 1. Dropzone-Elemente holen
    const fileIdInput = row.querySelector('.part-file-id');
    const fileNameDisplay = row.querySelector('.part-file-name-display');

    // Dateiname sauber extrahieren (title Attribut nutzen, falls vorhanden, um Kürzungen zu umgehen)
    let fileName = "";
    if (fileNameDisplay) {
        fileName = fileNameDisplay.title || fileNameDisplay.textContent.replace(/📌|📄/g, '').trim();
        // Falls noch der Platzhalter-Text drin steht, nicht als Dateiname sichern
        if (fileName.includes("Keine Datei")) {
            fileName = "";
        }
    }

    // 2. Objekt zurückgeben (inklusive der neuen Felder für das JSON)
    return {
        // Neue Felder für die Datei-Persistenz im JSON-Artefakt
        file_id: fileIdInput ? fileIdInput.value : "",
        file_name: fileName,

        // Bestehende Felder
        part_name: row.querySelector('.part-name')?.value || "",
        quantity: parseInt(row.querySelector('.part-qty')?.value || "1", 10),
        process: row.querySelector('.part-process')?.value || "FDM_PRINT",
        dim_x: parseFloat(row.querySelector('.part-dim-x')?.value || "0"),
        dim_y: parseFloat(row.querySelector('.part-dim-y')?.value || "0"),
        dim_z: parseFloat(row.querySelector('.part-dim-z')?.value || "0"),
        material_id: row.querySelector('.part-material')?.value || "",
        color: row.querySelector('.part-color')?.value || "BLACK",
        profile_id: row.querySelector('.part-profile')?.value || "",
        nozzle: row.querySelector('.part-nozzle')?.value || "0.4",
        weight: parseFloat(row.querySelector('.part-weight')?.value || "0"),
        print_time: parseInt(row.querySelector('.part-time')?.value || "0", 10)
    };
}

// Falls die Funktion bisher nicht global war, hier registrieren
window.extractPartData = extractPartData;
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
function fillRowData(row, part) {
    // Wenn die BOM im Aufbau ist, blockieren wir alle automatischen Server-Anfragen!
    if (window.isBOMLoading) {
        // Hier nur die reinen Textwerte in die Inputs schreiben, KEINE Events triggern!
        row.querySelector('.part-name').value = part.part_name || '';
        row.querySelector('.part-qty').value = part.quantity || 1;
        
        const processSelect = row.querySelector('.part-process');
        if (processSelect) processSelect.value = part.process || 'FDM_PRINT';
        
        // Die neuen Datei-IDs sichern
        const fileIdInput = row.querySelector('.part-file-id');
        if (fileIdInput) fileIdInput.value = part.file_id || part.fileId || '';
        
        // ... Restliche Felder (dim_x, weight, etc.) nur als .value zuweisen ...
        return; 
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

/**
 * Fügt ein loses Einzelteil hinzu (akzeptiert optionale Bestandsdaten)
 */
function addNewPart(data = {}) {
    const container = document.getElementById('bom_parts_container');
    if (!container) return;

    const uniqueId = data.id || `part_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    
    container.insertAdjacentHTML('beforeend', renderPartTemplate(data, uniqueId));
    
    const newRow = container.lastElementChild;
    bindPartEvents(newRow);
    updateBOMStats();
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
        
            // 3. Direktes DOM-Update statt Reload, da bp.bom_exists sonst
            //    erst beim nächsten GET von manufacturing_control neu berechnet würde.
        
            // a) "PRODUKTION STARTEN"-Button auf der zugehörigen Card freischalten
            const triggerBtn = document.getElementById(`trigger-btn-${bpId}`);
            if (triggerBtn) {
                triggerBtn.disabled = false;
            }
        
            // b) BOM-Badge (Icon-Farbe + Labeltext) von "(fehlt)" auf "(vorhanden)" umstellen
            const bomIcon = document.getElementById(`bom-icon-${bpId}`);
            const bomLabel = document.getElementById(`bom-label-${bpId}`);
            if (bomIcon) {
                bomIcon.classList.remove('text-muted');
                bomIcon.classList.add('text-accent-custom');
            }
            if (bomLabel) {
                bomLabel.textContent = 'BOM (vorhanden)';
            }
        
            // HINWEIS: refreshJobPool() und Counter-Inkrement
            // fliegen hier raus, da sie hier nichts zu suchen haben!
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

/**
 * Fügt ein Teil INNERHALB einer Baugruppe hinzu.
 * Unterstützt nun die Übergabe von gespeicherten Daten beim Laden der BOM!
 * @param {string} assemblyId - Die ID des Baugruppen-Containers
 * @param {Object} data - Optional: Die gespeicherten Bauteildaten aus dem JSON
 */
window.addNewPartToAssembly = function(assemblyId, data = {}) {
    const container = document.querySelector(`#${assemblyId} .parts-container`);
    if (!container) return console.error(`Baugruppen-Container #${assemblyId} nicht gefunden!`);

    // Falls aus der DB geladen, behalten wir die ID, ansonsten generieren wir eine neue
    const uniqueId = data.id || `part_asm_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`;
    
    // WICHTIG: Hier stand vorher {} – jetzt übergeben wir die echten Daten!
    container.insertAdjacentHTML('beforeend', renderPartTemplate(data, uniqueId));
    
    const newRow = container.lastElementChild;
    bindPartEvents(newRow);
    updateBOMStats(); 
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

// DRAG & DROP LOGIK FÜR DIE BAUTEILE (BOM)
// ==========================================
// 1. Dragover: Highlight gezielt auf die Dropzone legen
document.addEventListener('dragover', (e) => {
    const dropzone = e.target.closest('.part-file-dropzone');
    if (dropzone) {
        e.preventDefault();
        dropzone.style.borderColor = '#ffc107'; // Wechselt auf gelb/orange gestrichelt
        dropzone.style.background = 'rgba(255, 193, 7, 0.15)';
    }
});

// 2. Dragleave: Zurücksetzen des Designs
document.addEventListener('dragleave', (e) => {
    const dropzone = e.target.closest('.part-file-dropzone');
    if (dropzone) {
        dropzone.style.borderColor = '#6c757d'; // Zurück auf bootstrap-secondary
        dropzone.style.background = 'rgba(0, 0, 0, 0.25)';
    }
});

// 3. Drop: Payload auswerten und UI aktualisieren
document.addEventListener('drop', (e) => {
    const dropzone = e.target.closest('.part-file-dropzone');
    if (!dropzone) return;
    
    e.preventDefault();

    try {
        const rawData = e.dataTransfer.getData('application/json');
        if (!rawData) return;
        
        const fileData = JSON.parse(rawData); // Enthält { id, name }

        // Minimaler Schutz-Check ohne UI-Overhead
        if (!fileData.name || !fileData.name.toLowerCase().endsWith('.gcode')) {
            console.warn(`Drop abgebrochen: "${fileData.name}" ist kein G-Code.`);
            return;
        }

        const idInput = dropzone.querySelector('.part-file-id');
        const nameDisplay = dropzone.querySelector('.part-file-name-display');

        if (idInput) {
            idInput.value = fileData.id;
            idInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        if (nameDisplay) {
            nameDisplay.innerHTML = `<i class="fa-solid fa-file-circle-check text-success me-1"></i>${fileData.name}`;
            nameDisplay.className = "part-file-name-display text-success fw-bold text-truncate px-1";
            nameDisplay.title = fileData.name;
        }

    } catch (err) {
        console.error("Fehler beim Verarbeiten des Datei-Drops:", err);
    }
});

function addPartFromBlueprint() {
    const bpId = document.getElementById('bom_proj_id_display').textContent.trim();
    if (!bpId) return alert("Keine Projekt-ID!");

    fetch(`/admin/project_autofill/${bpId}`)
        .then(response => {
            if (!response.ok) throw new Error(`Server-Status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (!data.success) {
                return alert("Autofill fehlgeschlagen: " + (data.message || "Unbekannter Fehler"));
            }

            // Mapping auf die Keys, die renderPartTemplate/addNewPart erwartet
            addNewPart({
                materialId: data.material_id,
                profileId: data.profile_id,
                weight: data.weight,
                print_time: data.print_time
            });
        })
        .catch(err => {
            console.error("Kritischer Fehler:", err);
            alert("Netzwerkfehler: " + err.message);
        });
}
// Exports
window.openManufacturingViewer = openManufacturingViewer;
window.addNewPart = addNewPart;
window.createAssemblyContainer = createAssemblyContainer;
window.renderPartTemplate = renderPartTemplate;
window.fillRowData = fillRowData;
window.updateBOMStats = updateBOMStats;
window.saveFullBOM = saveFullBOM;
window.addPartFromBlueprint = addPartFromBlueprint;
