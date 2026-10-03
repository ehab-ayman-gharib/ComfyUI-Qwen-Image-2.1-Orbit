import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

function safeStr(val) {
    if (typeof val === "string") return val.trim();
    if (val === null || val === undefined) return "";
    return String(val).trim();
}

function buildOrbitInstruction(move, elevation) {
    if (move === "keep angle") {
        if (elevation === "eye level") {
            return "<orbit> keep the camera angle, eye level";
        }
        return `<orbit> keep the camera angle, ${elevation}`;
    }
    if (move === "180") {
        return `<orbit> rotate the camera 180 degrees, ${elevation}`;
    }
    const parts = safeStr(move).split(" ");
    if (parts.length >= 2) {
        return `<orbit> rotate the camera ${parts[0]} degrees to the ${parts[1]}, ${elevation}`;
    }
    return `<orbit> rotate the camera ${move}, ${elevation}`;
}

const DEFAULT_SUFFIX = ". The image has alpha channel and the background is transparent.";

/* =========================================================================
   1. QwenOrbitPrompt Extension (Dropdowns, Turntable Toggle & Live Preview)
   ========================================================================= */
app.registerExtension({
    name: "QwenImage21.OrbitPrompt",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "QwenOrbitPrompt") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

            let previewWidget = this.widgets?.find(w => w.name === "Prompt sent to model (Live)");
            if (!previewWidget) {
                previewWidget = this.addWidget(
                    "customtext",
                    "Prompt sent to model (Live)",
                    "",
                    () => {},
                    { multiline: true, readOnly: true, serialize: false }
                );
                previewWidget.serialize = false;
            }

            const updatePrompt = () => {
                try {
                    const modeWidget = this.widgets?.find(w => w.name === "mode");
                    const angleWidget = this.widgets?.find(w => w.name === "camera_angle");
                    const elevWidget = this.widgets?.find(w => w.name === "camera_elevation");
                    const turntableWidget = this.widgets?.find(w => w.name === "turntable_7_views");
                    const genFrontWidget = this.widgets?.find(w => w.name === "generate_front_0deg");
                    const suffixBoolWidget = this.widgets?.find(w => w.name === "include_suffix");
                    const prefixWidget = this.widgets?.find(w => w.name === "custom_prefix");
                    const suffixWidget = this.widgets?.find(w => w.name === "custom_suffix");

                    let mode = safeStr(modeWidget?.value);
                    if (!mode) {
                        mode = Boolean(turntableWidget?.value) ? "Full Turntable 360" : "Single View";
                    }
                    const angle = safeStr(angleWidget?.value) || "keep angle";
                    const elev = safeStr(elevWidget?.value) || "eye level";
                    const incSuffix = suffixBoolWidget ? Boolean(suffixBoolWidget.value) : true;
                    const prefix = typeof prefixWidget?.value === "string" ? prefixWidget.value.trim() : "";
                    const suffix = typeof suffixWidget?.value === "string" ? suffixWidget.value : DEFAULT_SUFFIX;

                    const is360 = mode.includes("360") || mode.toLowerCase().includes("turntable");
                    const isPatch = mode.toLowerCase().includes("patch");

                    if (is360 && !isPatch) {
                        const lines = [
                            `[8 Prompts sent sequentially for full 360° orbit]:`,
                            `0. keep angle (0° Front)  ->  1. 45 right  ->  2. 90 right  ->  3. 135 right`,
                            `4. 180 (Back)             ->  5. 135 left  ->  6. 90 left   ->  7. 45 left`,
                        ];
                        if (prefix) lines.push(`Prefix: "${prefix}"`);
                        previewWidget.value = lines.join("\n");
                    } else if (isPatch) {
                        const inst = buildOrbitInstruction(angle, elev);
                        let full = prefix ? `${prefix} ${inst}` : inst;
                        if (incSuffix && suffix) full += suffix;
                        previewWidget.value = `[Single Prompt sent to model]:\n${full}`;
                    } else {
                        const inst = buildOrbitInstruction(angle, elev);
                        let full = prefix ? `${prefix} ${inst}` : inst;
                        if (incSuffix && suffix) full += suffix;
                        previewWidget.value = `[Single Prompt sent to model]:\n${full}`;
                    }

                    if (this.setDirtyCanvas) {
                        this.setDirtyCanvas(true, true);
                    }
                } catch (e) {
                    console.warn("[QwenOrbitPrompt] Error updating live preview:", e);
                }
            };

            const attachCallback = (w) => {
                if (!w) return;
                const orig = w.callback;
                w.callback = function () {
                    const res = orig ? orig.apply(this, arguments) : undefined;
                    updatePrompt();
                    return res;
                };
            };

            this.widgets?.forEach(w => {
                if (w !== previewWidget) {
                    attachCallback(w);
                }
            });

            setTimeout(updatePrompt, 100);
            return r;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = onConfigure ? onConfigure.apply(this, arguments) : undefined;
            setTimeout(() => {
                const angleWidget = this.widgets?.find(w => w.name === "camera_angle");
                const previewWidget = this.widgets?.find(w => w.name === "Prompt sent to model (Live)");
                if (previewWidget && angleWidget) {
                    const w = this.widgets?.find(w => w.name === "custom_prefix");
                    if (w && typeof w.value !== "string") {
                        w.value = "";
                    }
                }
            }, 50);
            return r;
        };
    }
});


/* =========================================================================
   2. QwenTurntable360Viewer Extension (Interactive 360° Scrubbing & Orbit Ring)
   ========================================================================= */

function buildImageUrl(entry) {
    if (!entry) return "";
    const params = new URLSearchParams({
        filename: entry.filename || entry.name || "",
        subfolder: entry.subfolder || "",
        type: entry.type || "temp",
        rand: (entry.rand ?? Date.now()).toString(),
    });
    return api.apiURL(`/view?${params.toString()}`);
}

app.registerExtension({
    name: "QwenImage21.Turntable360Viewer",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "QwenTurntable360Viewer") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

            this.turntableFrames = [];
            this.currentIndex = 0;
            this.isPlaying = false;
            this.playInterval = null;

            const SPEED_PRESETS = [
                { label: "⏱ 0.5x", ms: 450 },
                { label: "⏱ 1x", ms: 300 },
                { label: "⏱ 0.25x", ms: 750 },
                { label: "⏱ 2x", ms: 160 },
            ];
            let currentSpeedIdx = 0; // Default: 0.5x (450ms, graceful turntable rotation)
            this.playSpeed = SPEED_PRESETS[currentSpeedIdx].ms;

            // --- Root Container ---
            const root = document.createElement("div");
            root.className = "qwen-turntable-container";
            root.style.cssText = `
                display: flex;
                flex-direction: column;
                width: 100%;
                background: #14171d;
                border: 1px solid #2d3440;
                border-radius: 10px;
                padding: 10px;
                box-sizing: border-box;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                color: #e2e8f0;
                user-select: none;
            `;

            // --- Header Controls ---
            const header = document.createElement("div");
            header.style.cssText = `
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
                padding: 0 4px;
            `;

            const title = document.createElement("div");
            title.innerHTML = `<span style="color:#f59e0b;font-weight:700;">360°</span> TURNTABLE`;
            title.style.cssText = "font-size:12px;font-weight:600;letter-spacing:0.5px;";

            const activeBadge = document.createElement("div");
            activeBadge.textContent = "Waiting for render...";
            activeBadge.style.cssText = `
                font-size: 11px;
                padding: 2px 8px;
                border-radius: 12px;
                background: rgba(245, 158, 11, 0.15);
                color: #f59e0b;
                border: 1px solid rgba(245, 158, 11, 0.4);
                font-weight: 500;
            `;

            const headerControls = document.createElement("div");
            headerControls.style.cssText = "display: flex; align-items: center; gap: 6px;";

            const speedBtn = document.createElement("button");
            speedBtn.type = "button";
            speedBtn.innerHTML = SPEED_PRESETS[currentSpeedIdx].label;
            speedBtn.title = "Playback Speed: Click to cycle (0.5x, 1x, 0.25x, 2x)";
            speedBtn.style.cssText = `
                background: #1e2430;
                border: 1px solid #334155;
                color: #cbd5e1;
                padding: 3px 8px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 11px;
                font-weight: 600;
                transition: all 0.15s;
            `;
            speedBtn.onmouseenter = () => speedBtn.style.borderColor = "#f59e0b";
            speedBtn.onmouseleave = () => speedBtn.style.borderColor = "#334155";
            speedBtn.onclick = () => {
                currentSpeedIdx = (currentSpeedIdx + 1) % SPEED_PRESETS.length;
                this.playSpeed = SPEED_PRESETS[currentSpeedIdx].ms;
                speedBtn.innerHTML = SPEED_PRESETS[currentSpeedIdx].label;
                if (this.isPlaying && this.playInterval) {
                    clearInterval(this.playInterval);
                    this.playInterval = setInterval(() => {
                        this.currentIndex = (this.currentIndex + 1) % this.turntableFrames.length;
                        updateFrame();
                    }, this.playSpeed);
                }
            };

            const playBtn = document.createElement("button");
            playBtn.type = "button";
            playBtn.innerHTML = "▶ Play";
            playBtn.style.cssText = `
                background: #2563eb;
                border: none;
                color: #fff;
                padding: 3px 10px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 11px;
                font-weight: 600;
                transition: background 0.15s;
            `;
            playBtn.onmouseenter = () => playBtn.style.background = "#1d4ed8";
            const saveFrameBtn = document.createElement("button");
            saveFrameBtn.type = "button";
            saveFrameBtn.innerHTML = "💾 Save Frame";
            saveFrameBtn.title = "Download currently displayed angle frame as PNG";
            saveFrameBtn.style.cssText = `
                background: #1e2430;
                border: 1px solid #334155;
                color: #cbd5e1;
                padding: 3px 8px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 11px;
                font-weight: 600;
                transition: all 0.15s;
            `;
            saveFrameBtn.onmouseenter = () => saveFrameBtn.style.borderColor = "#f59e0b";
            saveFrameBtn.onmouseleave = () => saveFrameBtn.style.borderColor = "#334155";
            saveFrameBtn.onclick = () => {
                if (!this.turntableFrames || this.turntableFrames.length === 0) return;
                const cur = this.turntableFrames[this.currentIndex];
                if (!cur || !cur.url) return;
                const a = document.createElement("a");
                a.href = cur.url;
                const safeAngle = (cur.angle || `frame_${this.currentIndex}`).replace(/[^a-zA-Z0-9_-]/g, "_");
                a.download = `qwen_orbit_${safeAngle}.png`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            };

            headerControls.appendChild(speedBtn);
            headerControls.appendChild(saveFrameBtn);
            headerControls.appendChild(playBtn);

            header.appendChild(title);
            header.appendChild(activeBadge);
            header.appendChild(headerControls);
            root.appendChild(header);

            // --- Main Viewport (Image + Orbit Ring Overlay) ---
            const viewport = document.createElement("div");
            viewport.style.cssText = `
                position: relative;
                width: 100%;
                aspect-ratio: 1 / 1;
                background: #0f1217;
                background-image: 
                    linear-gradient(45deg, #181c24 25%, transparent 25%), 
                    linear-gradient(-45deg, #181c24 25%, transparent 25%), 
                    linear-gradient(45deg, transparent 75%, #181c24 75%), 
                    linear-gradient(-45deg, transparent 75%, #181c24 75%);
                background-size: 20px 20px;
                background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
                border: 1px solid #262c38;
                border-radius: 8px;
                overflow: hidden;
                cursor: ew-resize;
                display: flex;
                align-items: center;
                justify-content: center;
            `;

            const mainImg = document.createElement("img");
            mainImg.style.cssText = `
                width: 100%;
                height: 100%;
                object-fit: contain;
                pointer-events: none;
                display: none;
            `;

            const placeholder = document.createElement("div");
            placeholder.innerHTML = `
                <div style="font-size:32px;margin-bottom:8px;opacity:0.4;">🔄</div>
                <div style="font-size:12px;color:#94a3b8;">Run workflow to view 360° turntable</div>
                <div style="font-size:10px;color:#64748b;margin-top:4px;">Drag horizontally to rotate • Click thumbnails</div>
            `;
            placeholder.style.cssText = "text-align:center;padding:20px;";

            // SVG Orbit Ring Overlay
            const svgOverlay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svgOverlay.setAttribute("viewBox", "0 0 400 400");
            svgOverlay.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                display: none;
            `;

            // Elliptical dashed orbit path
            const orbitPath = document.createElementNS("http://www.w3.org/2000/svg", "ellipse");
            orbitPath.setAttribute("cx", "200");
            orbitPath.setAttribute("cy", "330");
            orbitPath.setAttribute("rx", "165");
            orbitPath.setAttribute("ry", "46");
            orbitPath.setAttribute("fill", "none");
            orbitPath.setAttribute("stroke", "#f59e0b");
            orbitPath.setAttribute("stroke-width", "2");
            orbitPath.setAttribute("stroke-dasharray", "6 4");
            orbitPath.setAttribute("opacity", "0.55");
            svgOverlay.appendChild(orbitPath);

            // Orbit camera icon handle group
            const cameraHandle = document.createElementNS("http://www.w3.org/2000/svg", "g");
            cameraHandle.innerHTML = `
                <circle cx="0" cy="0" r="14" fill="#f59e0b" filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.5))" />
                <circle cx="0" cy="0" r="12" fill="#d97706" />
                <text x="0" y="4" font-size="11" text-anchor="middle" fill="#ffffff" font-family="sans-serif">📷</text>
            `;
            svgOverlay.appendChild(cameraHandle);

            viewport.appendChild(placeholder);
            viewport.appendChild(mainImg);
            viewport.appendChild(svgOverlay);
            root.appendChild(viewport);

            // --- Bottom Thumbnails Ribbon ---
            const ribbon = document.createElement("div");
            ribbon.style.cssText = `
                display: flex;
                gap: 5px;
                margin-top: 8px;
                overflow-x: auto;
                padding-bottom: 4px;
            `;
            root.appendChild(ribbon);

            // Function to update the view based on this.currentIndex
            const updateFrame = () => {
                const total = this.turntableFrames.length;
                if (total === 0) return;

                if (this.currentIndex < 0) this.currentIndex = (this.currentIndex % total + total) % total;
                if (this.currentIndex >= total) this.currentIndex = this.currentIndex % total;

                const cur = this.turntableFrames[this.currentIndex];
                if (!cur) return;

                mainImg.src = cur.url;
                mainImg.style.display = "block";
                placeholder.style.display = "none";
                svgOverlay.style.display = "block";

                activeBadge.textContent = `${cur.label} (${this.currentIndex + 1}/${total})`;

                // Update Camera Handle Position on Ellipse:
                // Canonical 8 angles around 360 degrees:
                // 0: 0° (front, 90 deg on ellipse)
                // 1: 45° R (135 deg)
                // 2: 90° R (180 deg)
                // 3: 135° R (225 deg)
                // 4: 180° (270 deg, back)
                // 5: 135° L (315 deg)
                // 6: 90° L (0 deg)
                // 7: 45° L (45 deg)
                const phiDeg = 90 + (this.currentIndex * 360 / total);
                const phiRad = (phiDeg * Math.PI) / 180;
                const hx = 200 - 165 * Math.cos(phiRad);
                const hy = 330 + 46 * Math.sin(phiRad);
                cameraHandle.setAttribute("transform", `translate(${hx}, ${hy})`);

                // Update thumbnail ribbon highlight
                Array.from(ribbon.children).forEach((btn, idx) => {
                    if (idx === this.currentIndex) {
                        btn.style.borderColor = "#f59e0b";
                        btn.style.background = "rgba(245, 158, 11, 0.25)";
                        btn.style.color = "#fbbf24";
                    } else {
                        btn.style.borderColor = "#334155";
                        btn.style.background = "#1e2430";
                        btn.style.color = "#94a3b8";
                    }
                });

                if (this.setDirtyCanvas) {
                    this.setDirtyCanvas(true, false);
                }
            };

            // Render Thumbnails Ribbon
            const renderRibbon = () => {
                ribbon.innerHTML = "";
                this.turntableFrames.forEach((frame, idx) => {
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.style.cssText = `
                        flex: 1;
                        min-width: 44px;
                        padding: 4px 2px;
                        background: #1e2430;
                        border: 1px solid #334155;
                        border-radius: 6px;
                        color: #94a3b8;
                        cursor: pointer;
                        font-size: 10px;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        gap: 3px;
                        transition: all 0.15s;
                    `;

                    if (frame.url) {
                        const thumb = document.createElement("img");
                        thumb.src = frame.url;
                        thumb.style.cssText = "width:34px;height:34px;object-fit:contain;border-radius:3px;";
                        btn.appendChild(thumb);
                    }

                    const lbl = document.createElement("span");
                    lbl.textContent = frame.angle || `${idx}`;
                    lbl.style.cssText = "font-weight:600;white-space:nowrap;";
                    btn.appendChild(lbl);

                    btn.onclick = () => {
                        stopPlay();
                        this.currentIndex = idx;
                        updateFrame();
                    };
                    ribbon.appendChild(btn);
                });
            };

            // --- Horizontal Drag / Scrub Interaction ---
            let isDragging = false;
            let startX = 0;
            let startIndex = 0;

            const onPointerDown = (e) => {
                if (this.turntableFrames.length === 0) return;
                isDragging = true;
                startX = e.clientX;
                startIndex = this.currentIndex;
                stopPlay();
                e.preventDefault();
                window.addEventListener("pointermove", onPointerMove);
                window.addEventListener("pointerup", onPointerUp);
            };

            const onPointerMove = (e) => {
                if (!isDragging || this.turntableFrames.length === 0) return;
                const dx = e.clientX - startX;
                const sensitivity = 32; // px per frame
                const frameOffset = Math.round(dx / sensitivity);
                this.currentIndex = startIndex + frameOffset;
                updateFrame();
            };

            const onPointerUp = () => {
                isDragging = false;
                window.removeEventListener("pointermove", onPointerMove);
                window.removeEventListener("pointerup", onPointerUp);
            };

            viewport.addEventListener("pointerdown", onPointerDown);

            // --- Auto-Play Toggle ---
            const startPlay = () => {
                if (this.turntableFrames.length === 0) return;
                this.isPlaying = true;
                playBtn.innerHTML = "⏸ Pause";
                playBtn.style.background = "#ea580c";
                this.playInterval = setInterval(() => {
                    this.currentIndex = (this.currentIndex + 1) % this.turntableFrames.length;
                    updateFrame();
                }, this.playSpeed);
            };

            const stopPlay = () => {
                this.isPlaying = false;
                playBtn.innerHTML = "▶ Play";
                playBtn.style.background = "#2563eb";
                if (this.playInterval) {
                    clearInterval(this.playInterval);
                    this.playInterval = null;
                }
            };

            playBtn.onclick = () => {
                if (this.isPlaying) {
                    stopPlay();
                } else {
                    startPlay();
                }
            };

            // --- Mount as ComfyUI DOM Widget ---
            const domWidget = this.addDOMWidget(
                "turntable_viewer_dom",
                "turntable_viewer",
                root,
                {
                    serialize: false,
                    hideOnZoom: false,
                }
            );

            domWidget.computeSize = function (width) {
                const w = Math.max(width || 440, 360);
                return [w, w + 140];
            };

            // --- Node Execution Hook (Receives Images) ---
            const onExecuted = nodeType.prototype.onExecuted;
            this.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                if (!message || !message.images || message.images.length === 0) return;

                stopPlay();
                // Preload all frames
                this.turntableFrames = message.images.map((img) => ({
                    url: buildImageUrl(img),
                    label: img.label || "Novel View",
                    angle: img.angle || "",
                }));

                this.turntableFrames.forEach((f) => {
                    const preload = new Image();
                    preload.src = f.url;
                });

                const patchedIdx = this.turntableFrames.findIndex(f => f.label && f.label.includes("Patched"));
                this.currentIndex = (patchedIdx !== -1) ? patchedIdx : 0;
                renderRibbon();
                updateFrame();
                startPlay();
            };

            return r;
        };
    }
});
