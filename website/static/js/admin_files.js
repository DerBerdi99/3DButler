export function loadProjectFilePool(projectId) {
    const poolContainer = document.getElementById('bom_file_pool');
    if (!poolContainer) return;

    poolContainer.innerHTML = '<div class="text-muted p-2 small text-center">Lade Projektdateien...</div>';

    fetch(`/admin/project/${projectId}/files`)
        .then(response => {
            if (!response.ok) throw new Error(`HTTP-Fehler! Status: ${response.status}`);
            return response.json();
        })
        .then(files => {
            poolContainer.innerHTML = '';
            
            if (!files || files.length === 0) {
                poolContainer.innerHTML = '<div class="text-muted p-2 small text-center">Keine Dateien im Projekt.</div>';
                return;
            }

            // Schleife läuft durch alle Dateien
            files.forEach(file => {
                const ext = file.FileName.split('.').pop().toLowerCase();
                
                // === STRIKTER GCODE-FILTER ===
                // Wenn die Datei kein .gcode ist, überspringen wir sie sofort (.blend, .stl, etc. fliegen raus)
                if (ext !== 'gcode') {
                    return; 
                }

                // Da es jetzt NUR noch Gcode ist, können wir uns die Abfragen sparen
                const icon = 'fa-square-poll-vertical text-warning';
                const bgClass = 'bg-warning bg-opacity-10 border-warning border-opacity-25';

                const fileItem = document.createElement('div');
                fileItem.className = `p-2 mb-1 border rounded d-flex align-items-center justify-content-between ${bgClass}`;
                            
                // 1. Das Element ziehbar machen und optisch als "Greifbar" markieren
                fileItem.setAttribute('draggable', 'true');
                fileItem.style.cursor = 'grab';
                            
                // 2. Die Daten beim Start des Ziehens hinterlegen
                fileItem.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('text/plain', file.FileID);
                    e.dataTransfer.setData('application/json', JSON.stringify({
                        id: file.FileID,
                        name: file.FileName
                    }));
                    fileItem.style.opacity = '0.5';
                });
                
                fileItem.addEventListener('dragend', () => {
                    fileItem.style.opacity = '1';
                });
                
                fileItem.innerHTML = `
                    <div class="d-flex align-items-center text-truncate me-2">
                        <i class="fa-solid ${icon} me-2 fs-5"></i>
                        <div class="text-truncate">
                            <div class="small text-light text-truncate fw-bold" title="${file.FileName}">${file.FileName}</div>
                            <span style="font-size: 0.65rem;" class="text-muted">${file.FileSizeKB} KB</span>
                        </div>
                    </div>
                    <div class="text-muted small px-1">
                        <i class="fa-solid fa-grip-vertical"></i>
                    </div>
                `;
                poolContainer.appendChild(fileItem);
            });

            // === VISUELLES FEEDBACK FALLS KEIN GCODE EXISTIERT ===
            // Falls Dateien da waren, aber keine einzige die Endung .gcode hatte
            if (poolContainer.children.length === 0) {
                poolContainer.innerHTML = '<div class="text-muted p-2 small text-center">Keine fertigungskonformen .gcode Dateien vorhanden.</div>';
            }
        })
        .catch(err => {
            console.error("Fehler im File-Pool-Fetch:", err);
            poolContainer.innerHTML = '<div class="text-danger p-2 small text-center">Fehler beim Laden.</div>';
        });
}
window.loadProjectFilePool = loadProjectFilePool;