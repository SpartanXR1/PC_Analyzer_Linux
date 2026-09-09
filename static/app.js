document.addEventListener("DOMContentLoaded", () => {
    const scanBtn = document.getElementById("scan-btn");
    const shutdownBtn = document.getElementById("shutdown-btn");
    const cleanupBtn = document.getElementById("cleanup-btn");
    const installRecommendationsBtn = document.getElementById("install-recommendations-btn");
    const languageBtn = document.getElementById("language-btn");
    const diagnosticModal = document.getElementById("diagnostic-modal");
    let currentLanguage = localStorage.getItem("laptop-analyzer-language") || "es";

    const translations = {
        es: {
            scan: "Analizar Sistema", scanning: "Analizando...", shutdown: "Apagar", hardware: "Hardware y Estado Actual",
            cpu: "CPU", driver: "Driver", governor: "Gobernador", temperature: "Temperatura", graphics: "Gráficos (GPU)",
            battery: "Batería", charge: "Carga", health: "Salud", power: "Consumo", diagnostics: "Diagnósticos e Incidencias",
            packages: "Paquetes Recomendados", install: "Instalar", maintenance: "Mantenimiento y Limpieza", cleanupAction: "Ejecutar Limpieza",
            maintenanceNote: "Acciones manuales para liberar caché y conservar el sistema ágil. No se ejecuta nada automáticamente.",
            manager: "Gestor", copy: "Copiar Comando", copied: "¡Copiado!", official: "Oficial", unknown: "Desconocido",
            noProblems: "¡Excelente! No se detectaron problemas de configuración o controladores faltantes.", initialIssues: "No se han encontrado problemas. Haz un escaneo para analizar tu sistema.",
            initialPackages: "No hay recomendaciones de paquetes actualmente.", initialCleanup: "Analiza el sistema para revisar cachés y archivos residuales.",
            noPackages: "No hay paquetes recomendados pendientes de instalar.", noCleanup: "No se detectaron cachés o archivos residuales relevantes.",
            notDetected: "No detectado", noBattery: "No detectada (¿PC de escritorio?)", detail: "Detalle del diagnóstico",
            solution: "Solución recomendada", command: "Comando sugerido", severityHigh: "alta", severityMedium: "media", severityLow: "baja",
            cleanupConfirm: "Se abrirá una terminal para limpiar la caché de usuario, del gestor de paquetes y logs antiguos. ¿Deseas continuar?",
            installConfirm: "Se abrirá una terminal para instalar todos los paquetes recomendados. ¿Deseas continuar?",
            memory: "Memoria RAM", ramUsed: "En uso", ramAvailable: "Disponible", swap: "Swap",
            liveMonitor: "Monitoreo en Vivo", disk: "Disco", readSpeed: "Lectura", writeSpeed: "Escritura",
            topCpu: "Procesos por CPU", topMemory: "Procesos por Memoria",
            disks: "Discos y Almacenamiento", initialDisk: "Analiza el sistema para ver los discos.",
            diskHealth: "Salud", noHealth: "N/D", usedLabel: "usado"
        },
        en: {
            scan: "Scan System", scanning: "Scanning...", shutdown: "Shutdown", hardware: "Hardware and Current Status",
            cpu: "CPU", driver: "Driver", governor: "Governor", temperature: "Temperature", graphics: "Graphics (GPU)",
            battery: "Battery", charge: "Charge", health: "Health", power: "Power draw", diagnostics: "Diagnostics and Issues",
            packages: "Recommended Packages", install: "Install", maintenance: "Maintenance and Cleanup", cleanupAction: "Run Cleanup",
            maintenanceNote: "Manual actions to free cache and keep the system responsive. Nothing runs automatically.",
            manager: "Package manager", copy: "Copy Command", copied: "Copied!", official: "Official", unknown: "Unknown",
            noProblems: "Excellent! No configuration problems or missing drivers were detected.", initialIssues: "No problems found. Scan your system to begin.",
            initialPackages: "There are currently no package recommendations.", initialCleanup: "Scan the system to review caches and residual files.",
            noPackages: "There are no recommended packages pending installation.", noCleanup: "No relevant caches or residual files were detected.",
            notDetected: "Not detected", noBattery: "Not detected (desktop PC?)", detail: "Diagnostic details",
            solution: "Recommended solution", command: "Suggested command", severityHigh: "high", severityMedium: "medium", severityLow: "low",
            cleanupConfirm: "A terminal will open to clean the user cache, package-manager cache, and old logs. Continue?",
            installConfirm: "A terminal will open to install all recommended packages. Continue?",
            memory: "Memory (RAM)", ramUsed: "Used", ramAvailable: "Available", swap: "Swap",
            liveMonitor: "Live Monitor", disk: "Disk", readSpeed: "Read", writeSpeed: "Write",
            topCpu: "Top CPU processes", topMemory: "Top memory processes",
            disks: "Disks and Storage", initialDisk: "Scan the system to see the disks.",
            diskHealth: "Health", noHealth: "N/D", usedLabel: "used"
        }
    };

    const issueTranslations = {
        "Failed Systemd Services": ["Servicios systemd fallidos", "One or more system services failed to start.", "Run `systemctl --failed` to identify the failed units and investigate their logs."],
        "Conflicting Power Management Daemons": ["Gestores de energía en conflicto", "Hay varios gestores de energía activos; pueden cambiar la política de CPU continuamente y aumentar el consumo.", "Mantén activo un solo gestor. Deshabilita los demás con `sudo systemctl disable --now servicio`."],
        "No Power Management Daemon Active": ["No hay un gestor de energía activo", "Ningún servicio de gestión de energía está activo, por lo que el portátil puede consumir más batería.", "Instala y activa un solo gestor compatible, como TLP o power-profiles-daemon."],
        "SSD Periodic Trim Disabled": ["TRIM periódico del SSD desactivado", "El sistema no ejecuta mantenimiento periódico del SSD.", "Activa el temporizador con `sudo systemctl enable --now fstrim.timer`."],
        "Missing Intel VA-API Hardware Video Decoding Drivers": ["Faltan controladores Intel VA-API", "La reproducción de vídeo puede usar la CPU en lugar de la aceleración de hardware.", "Instala el controlador VA-API disponible para tu generación Intel y reinicia el navegador."],
        "Missing AMD VA-API Drivers": ["Faltan controladores AMD VA-API", "La GPU AMD no tiene instalado el controlador de aceleración de vídeo recomendado.", "Instala el paquete VA-API sugerido y verifica la aceleración en tu navegador."],
        "Missing NVIDIA Drivers": ["Faltan controladores NVIDIA", "Se detectó una GPU NVIDIA sin el controlador propietario instalado.", "Instala el controlador recomendado por tu distribución y reinicia el equipo."],
        "Intel Thermal Daemon Not Installed": ["Falta thermald", "El daemon térmico ayuda a evitar temperaturas excesivas en procesadores Intel.", "Instala thermald y activa su servicio desde el comando sugerido."],
        "Intel Thermal Daemon Installed but Inactive": ["thermald está inactivo", "thermald está instalado pero no está ejecutándose.", "Activa el servicio con `sudo systemctl enable --now thermald`."],
        "Orphaned Packages Found": ["Hay paquetes huérfanos", "Se detectaron dependencias que ya no parecen necesarias.", "Revisa la lista y elimínalas con el gestor de paquetes antes de confirmar." ]
    };

    function t(key) {
        return translations[currentLanguage][key] || translations.es[key] || key;
    }

    function applyLanguage() {
        document.documentElement.lang = currentLanguage;
        document.querySelectorAll("[data-i18n]").forEach(element => {
            element.textContent = t(element.dataset.i18n);
        });
        document.title = currentLanguage === "es" ? "Analizador de Portátil - Linux" : "Laptop Performance Analyzer - Linux";
        languageBtn.textContent = currentLanguage === "es" ? "EN" : "ES";
        languageBtn.setAttribute("aria-label", currentLanguage === "es" ? "Switch to English" : "Cambiar a español");
        document.getElementById("diagnostic-modal-title").textContent = t("detail");
        document.getElementById("diagnostic-solution-label").textContent = t("solution");
        document.getElementById("diagnostic-command-label").textContent = t("command");
    }

    function localizeIssue(issue) {
        const translated = issueTranslations[issue.title];
        if (currentLanguage === "es" && translated) {
            return { ...issue, title: translated[0], description: translated[1], fix: translated[2] };
        }
        return issue;
    }

    function formatBytes(bytes) {
        if (!bytes && bytes !== 0) return "N/D";
        const units = ["B", "KB", "MB", "GB", "TB"];
        let value = bytes;
        let unit = 0;
        while (value >= 1024 && unit < units.length - 1) {
            value /= 1024;
            unit++;
        }
        return `${value.toFixed(1)} ${units[unit]}`;
    }

    function formatSpeed(bytesPerSec) {
        return `${formatBytes(bytesPerSec)}/s`;
    }

    // Send heartbeat pings to the server
    function sendHeartbeat() {
        fetch("/api/heartbeat", { method: "POST" }).catch(() => {
            // Ignore connection errors if server is stopping
        });
    }
    // Start heartbeat immediately and ping every 3 seconds
    sendHeartbeat();
    setInterval(sendHeartbeat, 3000);

    // Fetch and render data
    async function triggerScan() {
        scanBtn.disabled = true;
        scanBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${t("scanning")}`;
        
        try {
            const res = await fetch("/api/scan");
            if (!res.ok) throw new Error("Error al analizar el equipo");
            const data = await res.json();
            
            renderDashboard(data);
        } catch (error) {
            alert("No se pudo escanear el sistema: " + error.message);
        } finally {
            scanBtn.disabled = false;
            scanBtn.innerHTML = `<i class="fa-solid fa-sync"></i> ${t("scan")}`;
        }
    }

    function renderDashboard(data) {
        if (data.system) {
            applyDistroTheme(data.system.distribution_id);
            document.getElementById("system-subtitle").textContent =
                `${data.system.distribution} · ${t("manager")}: ${data.system.package_manager}`;
        }

        // Render CPU
        document.getElementById("cpu-model").textContent = data.cpu.model || t("notDetected");
        document.getElementById("cpu-driver").textContent = data.cpu.driver || t("notDetected");
        document.getElementById("cpu-gov").textContent = data.cpu.governor || t("notDetected");
        document.getElementById("cpu-temp").textContent = data.cpu.temp ? `${data.cpu.temp} °C` : "N/D";

        // Render GPU
        const gpuContainer = document.getElementById("gpu-container");
        gpuContainer.innerHTML = "";
        if (data.gpus && data.gpus.length > 0) {
            data.gpus.forEach(gpu => {
                const p = document.createElement("p");
                p.className = "stat-value";
                p.style.fontSize = "0.95rem";
                p.innerHTML = `<i class="fa-solid fa-microchip"></i> ${gpu.name}`;
                gpuContainer.appendChild(p);
            });
        } else {
            gpuContainer.innerHTML = `<p class="stat-value">${t("notDetected")}</p>`;
        }

        // Render Battery
        const bat = data.battery;
        if (bat.present) {
            document.getElementById("bat-status").textContent = translateStatus(bat.status);
            document.getElementById("bat-charge").textContent = `${bat.charge}%`;
            document.getElementById("bat-health").textContent = `${bat.health}% (Desgaste: ${bat.wear}%)`;
            document.getElementById("bat-draw").textContent = bat.power_draw > 0 ? `${bat.power_draw} W` : "N/D";
            
            const progress = document.getElementById("bat-progress");
            progress.style.width = `${bat.charge}%`;
            if (bat.charge < 20) {
                progress.style.backgroundColor = "var(--danger)";
            } else if (bat.charge < 60) {
                progress.style.backgroundColor = "var(--warning)";
            } else {
                progress.style.backgroundColor = "var(--success)";
            }
        } else {
            document.getElementById("bat-status").textContent = t("noBattery");
            document.getElementById("bat-charge").textContent = "N/D";
            document.getElementById("bat-health").textContent = "N/D";
            document.getElementById("bat-draw").textContent = "N/D";
            document.getElementById("bat-progress").style.width = "0%";
        }

        // Render RAM
        const mem = data.memory;
        if (mem && mem.present) {
            document.getElementById("ram-status").textContent = `${mem.percent}% (${formatBytes(mem.used)} / ${formatBytes(mem.total)})`;
            document.getElementById("ram-used").textContent = `${formatBytes(mem.used)} (${mem.percent}%)`;
            document.getElementById("ram-available").textContent = formatBytes(mem.available);
            document.getElementById("swap-status").textContent = mem.swap_total > 0
                ? `${formatBytes(mem.swap_used)} / ${formatBytes(mem.swap_total)} (${mem.swap_percent}%)`
                : t("notDetected");
            const ramProgress = document.getElementById("ram-progress");
            ramProgress.style.width = `${mem.percent}%`;
            if (mem.percent > 85) {
                ramProgress.style.backgroundColor = "var(--danger)";
            } else if (mem.percent > 70) {
                ramProgress.style.backgroundColor = "var(--warning)";
            } else {
                ramProgress.style.backgroundColor = "var(--success)";
            }
        } else {
            document.getElementById("ram-status").textContent = t("notDetected");
            document.getElementById("ram-used").textContent = "N/D";
            document.getElementById("ram-available").textContent = "N/D";
            document.getElementById("swap-status").textContent = "N/D";
            document.getElementById("ram-progress").style.width = "0%";
        }

        // Render Disks & filesystem usage
        const disksList = document.getElementById("disks-list");
        disksList.innerHTML = "";
        if (data.disks && data.disks.length > 0) {
            data.disks.forEach(disk => {
                const item = document.createElement("div");
                item.className = "disk-item";
                const healthBadge = disk.health
                    ? `<span class="badge ${disk.health === "PASSED" ? "badge-official" : "badge-high"}">${t("diskHealth")}: ${disk.health}</span>`
                    : `<span class="badge badge-low">${t("diskHealth")}: ${t("noHealth")}</span>`;
                const typeLabel = { nvme: "NVMe", ssd: "SSD", hdd: "HDD" }[disk.type] || disk.type;
                item.innerHTML = `
                    <div class="disk-info">
                        <i class="fa-solid fa-hard-drive"></i>
                        <div>
                            <h4>${disk.model}</h4>
                            <p>/dev/${disk.name} · ${typeLabel} · ${formatBytes(disk.size)}</p>
                        </div>
                    </div>
                    ${healthBadge}
                `;
                disksList.appendChild(item);
            });
        } else {
            disksList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-hard-drive"></i>
                    <p>${t("notDetected")}</p>
                </div>
            `;
        }

        const fsContainer = document.getElementById("fs-usage");
        fsContainer.innerHTML = "";
        if (data.filesystems && data.filesystems.length > 0) {
            data.filesystems.forEach(fs => {
                const row = document.createElement("div");
                row.className = "fs-row";
                const pct = fs.percent;
                let barColor = "var(--success)";
                if (pct > 85) barColor = "var(--danger)";
                else if (pct > 70) barColor = "var(--warning)";
                row.innerHTML = `
                    <div class="fs-row-header">
                        <span class="fs-mount">${fs.mount}</span>
                        <span class="fs-meta">${formatBytes(fs.used)} / ${formatBytes(fs.total)} (${pct}% ${t("usedLabel")})</span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width:${pct}%; background-color: ${barColor};"></div>
                    </div>
                `;
                fsContainer.appendChild(row);
            });
        }

        // Render Issues
        const issuesList = document.getElementById("issues-list");
        issuesList.innerHTML = "";
        if (data.issues && data.issues.length > 0) {
            data.issues.forEach(issue => {
                const localizedIssue = localizeIssue(issue);
                const item = document.createElement("div");
                item.className = "issue-item diagnostic-item";
                item.tabIndex = 0;
                
                let btnHtml = "";
                if (issue.fix_cmd) {
                    btnHtml = `<button class="btn btn-primary btn-sm copy-action-btn" data-cmd="${issue.fix_cmd}"><i class="fa-solid fa-copy"></i> ${t("copy")}</button>`;
                }
                
                item.innerHTML = `
                    <div class="issue-content">
                        <div class="issue-header">
                            <span class="badge badge-${issue.severity}">${t(`severity${issue.severity[0].toUpperCase()}${issue.severity.slice(1)}`)}</span>
                            <span class="issue-title">${localizedIssue.title}</span>
                        </div>
                        <p class="issue-desc">${localizedIssue.description}</p>
                    </div>
                    ${btnHtml}
                `;
                item.addEventListener("click", event => {
                    if (!event.target.closest("button")) openDiagnosticModal(issue);
                });
                item.addEventListener("keydown", event => {
                    if (event.key === "Enter" || event.key === " ") openDiagnosticModal(issue);
                });
                issuesList.appendChild(item);
            });
        } else {
            issuesList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-circle-check" style="color: var(--success); opacity: 1;"></i>
                    <p>${t("noProblems")}</p>
                </div>
            `;
        }

        // Render Recommendations
        const recsList = document.getElementById("recs-list");
        recsList.innerHTML = "";
        installRecommendationsBtn.disabled = !(data.recommendations && data.recommendations.length > 0);
        if (data.recommendations && data.recommendations.length > 0) {
            data.recommendations.forEach(rec => {
                const item = document.createElement("div");
                item.className = "rec-item";
                
                let sourceBadge = "";
                if (rec.source === "aur") {
                    sourceBadge = `<span class="badge badge-aur">AUR</span>`;
                } else if (rec.source === "official") {
                    sourceBadge = `<span class="badge badge-official">${t("official")}</span>`;
                } else {
                    sourceBadge = `<span class="badge badge-low">${t("unknown")}</span>`;
                }

                item.innerHTML = `
                    <div class="rec-info">
                        <h4>${rec.package}</h4>
                        <p>${rec.description}</p>
                    </div>
                    <div class="rec-actions">
                        ${sourceBadge}
                        <button class="btn btn-outline btn-sm copy-action-btn" data-cmd="${rec.install_cmd}">
                            <i class="fa-solid fa-copy"></i> ${t("copy")}
                        </button>
                    </div>
                `;
                recsList.appendChild(item);
            });
        } else {
            recsList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-box-open"></i>
                    <p>${t("noPackages")}</p>
                </div>
            `;
        }

        // Render cache and residual file cleanup actions
        const cleanupList = document.getElementById("cleanup-list");
        cleanupList.innerHTML = "";
        if (data.cleanup && data.cleanup.length > 0) {
            data.cleanup.forEach(item => {
                const cleanupItem = document.createElement("div");
                cleanupItem.className = "issue-item cleanup-item";
                cleanupItem.innerHTML = `
                    <div class="issue-content">
                        <div class="issue-header">
                            <span class="badge badge-${item.severity}">${item.severity}</span>
                            <span class="issue-title">${item.title}</span>
                        </div>
                        <p class="issue-desc">${item.description}</p>
                    </div>
                    <button class="btn btn-outline btn-sm copy-action-btn" data-cmd="${item.command}">
                        <i class="fa-solid fa-copy"></i> ${t("copy")}
                    </button>
                `;
                cleanupList.appendChild(cleanupItem);
            });
        } else {
            cleanupList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-circle-check" style="color: var(--success); opacity: 1;"></i>
                    <p>${t("noCleanup")}</p>
                </div>
            `;
        }

        applyLanguage();

        // Add copy action listeners
        document.querySelectorAll(".copy-action-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const cmd = btn.getAttribute("data-cmd");
                navigator.clipboard.writeText(cmd).then(() => {
                    const originalText = btn.innerHTML;
                    btn.innerHTML = `<i class="fa-solid fa-check"></i> ${t("copied")}`;
                    btn.style.backgroundColor = "var(--success)";
                    btn.style.color = "#fff";
                    setTimeout(() => {
                        btn.innerHTML = originalText;
                        btn.style.backgroundColor = "";
                        btn.style.color = "";
                    }, 1500);
                }).catch(err => {
                    alert("Error al copiar: " + err);
                });
            });
        });
    }

    // ---------- Live Monitor ----------
    const liveCpuHistory = [];
    const liveRamHistory = [];

    function resolveColor(name) {
        let color = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        if (!color) color = "#6366f1";
        const hexMatch = color.match(/^#?([a-f0-9]{3}|[a-f0-9]{6})$/i);
        if (hexMatch) {
            let hex = hexMatch[1];
            if (hex.length === 3) hex = hex.split("").map(c => c + c).join("");
            const r = parseInt(hex.slice(0, 2), 16);
            const g = parseInt(hex.slice(2, 4), 16);
            const b = parseInt(hex.slice(4, 6), 16);
            return `rgba(${r}, ${g}, ${b}, 1)`;
        }
        if (color.startsWith("rgb(")) {
            return color.replace("rgb(", "rgba(").replace(")", ", 1)");
        }
        return color;
    }

    function withAlpha(color, alpha) {
        return color.replace(/,\s*1\)$/, `, ${alpha})`);
    }

    function drawLiveChart(canvas, values, color) {
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;
        ctx.clearRect(0, 0, w, h);
        if (!values || values.length < 2) return;

        ctx.strokeStyle = "rgba(255,255,255,0.06)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = 8 + (i * (h - 16)) / 4;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(w, y);
            ctx.stroke();
        }

        const points = values.slice(-60);
        const step = points.length > 1 ? (w - 8) / (points.length - 1) : 0;
        const toY = value => h - 8 - (Math.min(value, 100) / 100) * (h - 20);
        const coords = points.map((v, i) => [4 + i * step, toY(v)]);

        const gradient = ctx.createLinearGradient(0, 0, 0, h);
        gradient.addColorStop(0, withAlpha(color, 0.35));
        gradient.addColorStop(1, withAlpha(color, 0.02));
        ctx.beginPath();
        ctx.moveTo(4, h - 8);
        coords.forEach(([x, y]) => ctx.lineTo(x, y));
        ctx.lineTo(4 + (points.length - 1) * step, h - 8);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        ctx.beginPath();
        coords.forEach(([x, y], i) => {
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.stroke();

        const last = coords[coords.length - 1];
        ctx.beginPath();
        ctx.arc(last[0], last[1], 3.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
    }

    function setProgressBar(id, percent, warnThreshold) {
        const bar = document.getElementById(id);
        bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
        if (percent > 85) {
            bar.style.backgroundColor = "var(--danger)";
        } else if (percent > warnThreshold) {
            bar.style.backgroundColor = "var(--warning)";
        } else {
            bar.style.backgroundColor = "var(--success)";
        }
    }

    function renderProcessList(containerId, processes) {
        const list = document.getElementById(containerId);
        list.innerHTML = "";
        if (!processes || !processes.length) {
            list.innerHTML = `<li class="proc-item"><span class="proc-name">-</span></li>`;
            return;
        }
        processes.forEach((proc, index) => {
            const li = document.createElement("li");
            li.className = "proc-item";
            li.innerHTML = `
                <span class="proc-rank">${index + 1}</span>
                <span class="proc-name">${proc.name}</span>
                <span class="proc-cpu">${proc.cpu}%</span>
                <span class="proc-mem">${proc.mem}%</span>
            `;
            list.appendChild(li);
        });
    }

    async function updateLiveStats() {
        try {
            const res = await fetch("/api/stats");
            if (!res.ok) throw new Error("Error al obtener estadísticas en vivo");
            const data = await res.json();

            document.getElementById("live-cpu").textContent = `${data.cpu.usage}%`;
            setProgressBar("live-cpu-bar", data.cpu.usage, 60);
            liveCpuHistory.push(data.cpu.usage);
            if (liveCpuHistory.length > 60) liveCpuHistory.shift();
            drawLiveChart(document.getElementById("cpu-chart"), liveCpuHistory, resolveColor("--primary"));

            const memPercent = data.memory.percent;
            document.getElementById("live-ram").textContent = `${memPercent}%`;
            setProgressBar("live-ram-bar", memPercent, 70);
            liveRamHistory.push(memPercent);
            if (liveRamHistory.length > 60) liveRamHistory.shift();
            drawLiveChart(document.getElementById("ram-chart"), liveRamHistory, resolveColor("--success"));

            document.getElementById("live-disk").textContent = `${data.disk.usage_percent}%`;
            setProgressBar("live-disk-bar", data.disk.usage_percent, 70);
            document.getElementById("live-read").textContent = formatSpeed(data.disk.read_speed);
            document.getElementById("live-write").textContent = formatSpeed(data.disk.write_speed);

            renderProcessList("proc-cpu", data.processes.cpu);
            renderProcessList("proc-mem", data.processes.memory);
        } catch (error) {
            // Transient errors are ignored; the next tick retries
        }
    }

    setInterval(updateLiveStats, 2500);
    updateLiveStats();

    function applyDistroTheme(distributionId) {
        const aliases = {
            "linuxmint": "mint",
            "opensuse-leap": "opensuse",
            "opensuse-tumbleweed": "opensuse",
            "sles": "opensuse",
            "pop": "popos",
            "pop!_os": "popos"
        };
        const theme = aliases[distributionId] || distributionId || "default";
        document.documentElement.dataset.distro = theme;
        document.body.dataset.distro = theme;
    }

    function openDiagnosticModal(issue) {
        const localizedIssue = localizeIssue(issue);
        const severity = document.getElementById("diagnostic-severity");
        severity.className = `badge badge-${issue.severity}`;
        severity.textContent = t(`severity${issue.severity[0].toUpperCase()}${issue.severity.slice(1)}`);
        document.getElementById("diagnostic-title").textContent = localizedIssue.title;
        document.getElementById("diagnostic-description").textContent = localizedIssue.description;
        document.getElementById("diagnostic-fix").textContent = localizedIssue.fix || t("noProblems");
        const commandWrap = document.getElementById("diagnostic-command-wrap");
        commandWrap.style.display = issue.fix_cmd ? "block" : "none";
        document.getElementById("diagnostic-command").textContent = issue.fix_cmd || "";
        diagnosticModal.style.display = "flex";
    }

    function closeDiagnosticModal() {
        diagnosticModal.style.display = "none";
    }

    function translateStatus(status) {
        const tr = {
            "Charging": "Cargando",
            "Discharging": "Descargando",
            "Full": "Llena",
            "Not charging": "No cargando",
            "Unknown": "Desconocido"
        };
        return tr[status] || status;
    }

    // Manual shutdown action
    shutdownBtn.addEventListener("click", async () => {
        if (confirm(currentLanguage === "es" ? "¿Estás seguro de que deseas apagar el analizador? Esto detendrá el servidor backend." : "Are you sure you want to stop the analyzer? This will stop the backend server.")) {
            try {
                await fetch("/api/shutdown", { method: "POST" });
                document.body.innerHTML = `
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: var(--bg-dark); color: var(--text-primary); font-family: var(--font-sans);">
                        <i class="fa-solid fa-power-off" style="font-size: 4rem; color: var(--danger); margin-bottom: 1.5rem;"></i>
                            <h1>${currentLanguage === "es" ? "Analizador Desactivado" : "Analyzer Stopped"}</h1>
                            <p style="color: var(--text-secondary); margin-top: 0.5rem;">${currentLanguage === "es" ? "El servidor se ha detenido con éxito. Puedes cerrar esta pestaña de forma segura." : "The server stopped successfully. You can safely close this tab."}</p>
                    </div>
                `;
            } catch (e) {
                alert("Error al apagar el servidor: " + e.message);
            }
        }
    });

    cleanupBtn.addEventListener("click", async () => {
        const confirmed = confirm(t("cleanupConfirm"));
        if (!confirmed) return;

        cleanupBtn.disabled = true;
        cleanupBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Abriendo terminal...';
        try {
            const res = await fetch("/api/cleanup", { method: "POST" });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "No se pudo abrir la terminal");
            cleanupBtn.innerHTML = '<i class="fa-solid fa-check"></i> Terminal abierta';
            setTimeout(() => {
                cleanupBtn.innerHTML = `<i class="fa-solid fa-terminal"></i> ${t("cleanupAction")}`;
                cleanupBtn.disabled = false;
            }, 2500);
        } catch (error) {
            cleanupBtn.disabled = false;
            cleanupBtn.innerHTML = `<i class="fa-solid fa-terminal"></i> ${t("cleanupAction")}`;
            alert(error.message);
        }
    });

    installRecommendationsBtn.addEventListener("click", async () => {
        if (!confirm(t("installConfirm"))) return;

        installRecommendationsBtn.disabled = true;
        installRecommendationsBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Preparando...';
        try {
            const res = await fetch("/api/install-recommendations", { method: "POST" });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "No se pudieron instalar los paquetes");
            installRecommendationsBtn.innerHTML = `<i class="fa-solid fa-check"></i> ${data.count} comando(s) enviado(s)`;
            setTimeout(() => {
                installRecommendationsBtn.innerHTML = '<i class="fa-solid fa-terminal"></i> Instalar';
                installRecommendationsBtn.disabled = false;
            }, 3000);
        } catch (error) {
            installRecommendationsBtn.innerHTML = '<i class="fa-solid fa-terminal"></i> Instalar';
            installRecommendationsBtn.disabled = false;
            alert(error.message);
        }
    });

    document.getElementById("close-diagnostic-modal").addEventListener("click", closeDiagnosticModal);
    diagnosticModal.addEventListener("click", event => {
        if (event.target === diagnosticModal) closeDiagnosticModal();
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeDiagnosticModal();
    });

    languageBtn.addEventListener("click", () => {
        currentLanguage = currentLanguage === "es" ? "en" : "es";
        localStorage.setItem("laptop-analyzer-language", currentLanguage);
        applyLanguage();
        triggerScan();
    });

    applyLanguage();
    scanBtn.addEventListener("click", triggerScan);

    // Initial scan
    triggerScan();
});
