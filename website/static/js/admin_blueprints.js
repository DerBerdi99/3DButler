// admin_blueprints.js - Vollständige, strukturierte Fassung

// 0. DATEN-INITIALISIERUNG
const materialsData = JSON.parse(document.getElementById('inventory-data').textContent || '[]');
const profilesData = JSON.parse(document.getElementById('profiles-data').textContent || '[]');

window.inventoryMaterials = materialsData;
window.printProfiles = profilesData;

// --- HILFSFUNKTIONEN (TEMPLATES & LOGIK) ---

function renderPartTemplate(data = {}, uniqueId) {
    return `
    <div class="bom-part-row bg-dark border border-secondary p-2 mb-2 rounded shadow-sm" style="border-left: 5px solid #0dcaf0">
        <div class="bom-part-item">
            <div class="part-group flex-grow-1">
                <label class="text-info fw-bold mb-1">Bezeichnung</label>
                <input type="text" class="form-control form-control-sm part-name text-white bg-dark border-secondary" 
                       placeholder="Bauteil..." value="${data.name || ''}">
            </div>

            <div class="part-group group-qty">
                <label class="text-info fw-bold mb-1">Menge</label>
                <input type="number" class="form-control form-control-sm part-qty text-white bg-dark border-secondary" 
                       value="${data.qty || 1}" min="1">
            </div>

            <div class="part-group">
                <label class="text-info fw-bold mb-1">Verfahren</label>
                <select class="form-select form-select-sm part-process bg-dark text-white border-secondary">
                    <option value="FDM_PRINT" selected>FDM</option>
                    <option value="CNC">CNC</option>
                    <option value="BOUGHT">Kaufteil</option>
                </select>
            </div>

            <div class="group-check">
                <div class="form-check m-0">
                    <input class="form-check-input part-is-bought" type="checkbox" id="${uniqueId}">
                    <label class="form-check-label small text-white-50" for="${uniqueId}">Kaufteil</label>
                </div>
            </div>

            <div class="part-group">
                <label class="text-secondary mb-1">Material</label>
                <select class="form-select form-select-sm part-material bg-dark text-white border-secondary">
                    ${window.inventoryMaterials.map(m => `<option value="${m.MaterialID}">${m.MaterialName}</option>`).join('')}
                </select>
            </div>

            <div class="part-group">
                <label class="text-secondary mb-1">Profil</label>
                <select class="form-select form-select-sm part-profile bg-dark text-white border-secondary">
                    ${window.printProfiles.map(p => `<option value="${p.ProfileID}">${p.ProfileName}</option>`).join('')}
                </select>
            </div>

            <div class="part-group group-time">
                <label class="text-secondary mb-1">Gewicht(g)</label>
                <input type="number" step="0.1" class="form-control form-control-sm part-weight bg-dark text-white border-secondary" placeholder="0.0">
            </div>

            <div class="part-group group-time">
                <label class="text-secondary mb-1">Zeit(min)</label>
                <input type="number" class="form-control form-control-sm part-time bg-dark text-white border-secondary" placeholder="Min">
            </div>

            <div class="group-actions">
                <button type="button" class="btn btn-sm btn-outline-danger border-0" onclick="removePartRow(this)">
                    &#x2715;
                </button>
            </div>
        </div>
    </div>`;
}

function bindPartEvents(row) {
    const boughtCheck = row.querySelector('.part-is-bought');
    const inputs = row.querySelectorAll('.part-material, .part-profile, .part-weight, .part-time');
    const qtyInput = row.querySelector('.part-qty');
    const timeInput = row.querySelector('.part-time');

    // 1. Status-Wechsel (Kaufteil)
    boughtCheck.addEventListener('change', function() {
        const isBought = this.checked;
        row.classList.toggle('opacity-50', isBought);
        row.style.borderLeft = isBought ? "5px solid #6c757d" : "5px solid #0dcaf0";
        inputs.forEach(i => {
            i.disabled = isBought;
            if (isBought) i.value = '';
        });
        updateBOMStats(); // Trigger Statistik
    });

    // 2. Wert-Änderungen (Menge/Zeit) für Live-Update beim Tippen
    [qtyInput, timeInput].forEach(el => {
        el.addEventListener('input', updateBOMStats);
    });
}

function updateBOMStats() {
    let totalQty = 0;
    let totalTime = 0;
    let boughtCount = 0;
    let totalItems = 0;

    document.querySelectorAll('.bom-part-row').forEach(row => {
        const qty = parseInt(row.querySelector('.part-qty').value) || 0;
        const time = parseInt(row.querySelector('.part-time').value) || 0;
        const isBought = row.querySelector('.part-is-bought').checked;

        totalQty += qty;
        totalItems++;
        if (isBought) {
            boughtCount++;
        } else {
            totalTime += (time * qty);
        }
    });

    // Update UI
    document.getElementById('stats_total_parts').textContent = totalQty;
    document.getElementById('stats_total_time').textContent = `${totalTime} min (${(totalTime/60).toFixed(1)}h)`;
    
    const ratio = totalItems > 0 ? Math.round((boughtCount / totalItems) * 100) : 0;
    document.getElementById('stats_bought_ratio').textContent = `${ratio}%`;
}
function removePartRow(btn) {
    btn.closest('.bom-part-row').remove();
    updateBOMStats(); // Statistik nach dem Löschen aktualisieren
}
function extractPartData(row) {
    return {
        part_name: row.querySelector('.part-name').value.trim(),
        quantity: parseInt(row.querySelector('.part-qty').value) || 1,
        process: row.querySelector('.part-process').value,
        material_id: row.querySelector('.part-material').value,
        profile_id: row.querySelector('.part-profile').value,
        weight: parseFloat(row.querySelector('.part-weight').value) || 0,
        print_time: parseInt(row.querySelector('.part-time').value) || 0,
        is_bought: row.querySelector('.part-is-bought').checked
    };
}

// --- CORE FUNKTIONEN ---

function openManufacturingViewer(button) {
    const bpId = button.dataset.blueprintId;
    const form = document.getElementById('viewerForm');
    if (!form) return;

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

async function openBOMWorkbench(button) {
    const bpId = button.dataset.projectId;
    const container = document.getElementById('bom_parts_container');
    container.innerHTML = ''; 
    
    document.getElementById('bom_proj_id_display').textContent = bpId;
    document.getElementById('bom_proj_name').textContent = button.dataset.projectName;

    try {
        const response = await fetch(`/admin/get_bom/${bpId}`);
        const result = await response.json();

        if (result.success && result.data) {
            const data = result.data;
            
            // 1. Baugruppen wiederherstellen
            if (data.assemblies) {
                data.assemblies.forEach(asm => {
                    // Erstelle die Baugruppe und fange die generierte ID ab
                    const assemblyId = `asm_${Math.random().toString(36).slice(2, 7)}`;
                    createAssemblyContainer(asm.assembly_name, assemblyId);
                    
                    // WICHTIG: Suche den Container INNERHALB der gerade erstellten Baugruppe
                    const asmPartsContainer = document.querySelector(`#${assemblyId} .parts-container`);
                    
                    if (asm.parts) {
                        asm.parts.forEach(part => {
                            const uniqueId = `part_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`;
                            asmPartsContainer.insertAdjacentHTML('beforeend', renderPartTemplate({name: part.part_name, qty: part.quantity}, uniqueId));
                            fillRowData(asmPartsContainer.lastElementChild, part);
                        });
                    }
                });
            }

            // 2. Einzelteile (lose) wiederherstellen
            if (data.loose_parts) {
                data.loose_parts.forEach(part => {
                    addNewPart({name: part.part_name, qty: part.quantity});
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

// Hilfsfunktion zum Setzen der Selects und Checkboxen
function fillRowData(row, data) {
    row.querySelector('.part-process').value = data.process || 'FDM_PRINT';
    row.querySelector('.part-material').value = data.material_id || '';
    row.querySelector('.part-profile').value = data.profile_id || '';
    row.querySelector('.part-weight').value = data.weight || '';
    row.querySelector('.part-time').value = data.print_time || '';
    
    const boughtCheck = row.querySelector('.part-is-bought');
    boughtCheck.checked = data.is_bought || false;
    
    // Trigger den Event-Listener für das Styling (Grau-Färbung)
    bindPartEvents(row);
    boughtCheck.dispatchEvent(new Event('change')); 
}

function addNewPart(data = {}) {
    const container = document.getElementById('bom_parts_container');
    const uniqueId = `part_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    
    container.insertAdjacentHTML('beforeend', renderPartTemplate(data, uniqueId));
    
    const newRow = container.lastElementChild;
    bindPartEvents(newRow);
    updateBOMStats(); // <--- NEU: Direkt beim Erstellen rechnen
}

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

window.addNewPartToAssembly = function(assemblyId) {
    const container = document.querySelector(`#${assemblyId} .parts-container`);
    const uniqueId = `part_asm_${Date.now()}`;
    
    container.insertAdjacentHTML('beforeend', renderPartTemplate({}, uniqueId));
    
    const newRow = container.lastElementChild;
    bindPartEvents(newRow);
    updateBOMStats(); // <--- NEU: Direkt beim Erstellen rechnen
};

function saveFullBOM() {
    const bpId = document.getElementById('bom_proj_id_display').textContent.trim();
    if (!bpId) return alert("Keine Projekt-ID!");

    const assemblies = [];
    document.querySelectorAll('.assembly-group').forEach(asm => {
        const parts = [];
        asm.querySelectorAll('.bom-part-row').forEach(row => {
            const d = extractPartData(row);
            if (d.part_name) parts.push(d);
        });
        assemblies.push({ assembly_name: asm.querySelector('.asm-title').value, parts: parts });
    });

    const looseParts = [];
    document.querySelectorAll('#bom_parts_container > .bom-part-row').forEach(row => {
        const d = extractPartData(row);
        if (d.part_name) looseParts.push(d);
    });

    fetch(`/admin/save_bom/${bpId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assemblies: assemblies, loose_parts: looseParts })
    }).then(res => res.ok ? location.reload() : alert("Fehler: " + res.status));
}

// --- INITIALISIERUNG ---


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

window.removePartRow = function(btn) {
    const row = btn.closest('.bom-part-row');
    if (row) {
        row.remove();
        updateBOMStats(); // Wichtig: Statistik neu berechnen
    }
};

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

    document.addEventListener('mouseup', () => {
        isDragging = false;
        isResizing = false;
        header.style.cursor = 'move';
        document.body.style.cursor = 'default';
    });
}

// Exports
window.openManufacturingViewer = openManufacturingViewer;
window.openBOMWorkbench = openBOMWorkbench;
window.addNewPart = addNewPart;
window.createAssemblyContainer = createAssemblyContainer;
window.saveFullBOM = saveFullBOM;
window.updateBOMStats = updateBOMStats;