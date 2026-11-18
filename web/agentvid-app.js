/* AgentVid Studio — Interactive Application Controller */
(() => {
  const { svg, esc, fmtTime } = window.AVIcons;
  const Views = window.AVViews;

  const NAV_ITEMS = [
    { id: "submit", label: "Submit Video", icon: "link", group: "Studio" },
    { id: "home", label: "Overview", icon: "home", group: "Studio" },
    { id: "projects", label: "Projects", icon: "folder", group: "Studio" },
    { id: "editor", label: "Studio Editor", icon: "scissors", group: "Workspace" },
    { id: "analysis", label: "Auto-Pilot Deck", icon: "cpu", group: "Workspace" },
    { id: "shots", label: "Shot Vault", icon: "grid", group: "Workspace" },
    { id: "virality", label: "Pulse Virality", icon: "flame", group: "Intelligence" },
    { id: "captions", label: "Kinetic Captions", icon: "type", group: "Intelligence" },
    { id: "export", label: "Render Hub", icon: "download", group: "Delivery" },
    { id: "settings", label: "Settings", icon: "settings", group: "System" },
  ];

  const S = {
    view: "submit",
    ingestUrl: "",
    ingestPreview: null,
    ingestPreviewLoading: false,
    ingestTargetProject: "",
    ingestHeight: 1080,
    ingestImmediate: true,
    ingestReelCount: 5,
    ingestDurationMode: "auto_ai",
    ingestTargetDuration: 30,
    ingestAutoCaptions: true,
    ingestCaptionLang: "auto",
    activeIngest: null,
    dashboard: null,
    projectsList: [],
    projectSearch: "",
    project: null,
    selectedShotId: null,
    editorRightTab: "shot",
    showFaceOverlay: true,
    showReframeGuide: true,
    settings: { auto_mode: true, automation: {}, face_detection: {}, privacy: {}, performance: {}, export_defaults: {} },
    aiConfig: {},
    speechModel: { ready: false, doing: false, percent: 0, downloaded_mb: 0, total_mb: 480, items_done: 0, items_total: 4, stage: "idle", error: "" },
    speechModalOpen: false,
    speechPromptDismissed: false,
    speechAutoExtractProject: null,
    onboardingOpen: false,
    onboardingStep: 1,
    onboardingEmail: "",
    onboardingEmailBusy: false,
    onboardingEmailStatus: "",
    onboardingEmailError: "",
    onboardingIgFollowed: false,
    about: {},
    captionStyles: [],
    captionAnimations: [],
    captionLanguages: [],
    aiAudioReady: false,
    captionGenBusy: false,
    fonts: [],
    viralityLabels: {},
    automationStatus: null,
    viralitySort: "score_desc",
    viralityFilterMin: 0,
    viralityFilterMax: 100,
    assistantMessages: [],
    exportOpts: {
      mode: "full",
      shot_id: "",
      filename: "",
      codec: "h264",
      resolution: "1080p",
      aspect: "16:9",
      fps: 30,
      quality: "standard",
      audio_bitrate: "192k",
      output_dir: "",
    },
    exportEstimate: null,
    activeExport: null,
    undoStack: [],
    redoStack: [],
    playingShotEnd: null,
  };

  let pollTimer = null;
  let autosaveTimer = null;
  let dirty = false;

  // ------------------------------------------------------------------ API Helpers
  async function api(url, opts = {}) {
    const init = {
      method: opts.method || "GET",
      headers: opts.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    };
    if (opts.body !== undefined) {
      init.body = opts.body instanceof FormData ? opts.body : JSON.stringify(opts.body);
    }
    const r = await fetch(url, init);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      throw new Error(data.detail || `Request failed (${r.status})`);
    }
    return data;
  }

  function toast(msg, kind = "") {
    const host = document.getElementById("toast-host");
    if (!host) return;
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 220);
    }, 3400);
  }

  function showModal(title, bodyHtml, onSubmit) {
    const host = document.getElementById("modal-host");
    host.innerHTML = `
      <div class="modal-backdrop" id="av-modal-bg">
        <div class="modal-card">
          <div class="row-between" style="margin-bottom:14px">
            <strong style="font-size:15px">${esc(title)}</strong>
            <button class="btn btn-icon btn-sm" id="av-modal-close">${svg("x", 14)}</button>
          </div>
          <form id="av-modal-form">${bodyHtml}</form>
        </div>
      </div>
    `;
    const close = () => { host.innerHTML = ""; };
    document.getElementById("av-modal-close").onclick = close;
    document.getElementById("av-modal-bg").onclick = e => { if (e.target.id === "av-modal-bg") close(); };
    document.getElementById("av-modal-form").onsubmit = async e => {
      e.preventDefault();
      try {
        await onSubmit(new FormData(e.target));
        close();
      } catch (err) {
        toast(err.message, "error");
      }
    };
  }

  // ------------------------------------------------------------------ History (Undo / Redo)
  function pushUndoSnapshot() {
    if (!S.project) return;
    const snap = JSON.stringify({ shots: S.project.shots, timeline: S.project.timeline });
    S.undoStack.push(snap);
    if (S.undoStack.length > 30) S.undoStack.shift();
    S.redoStack = [];
    dirty = true;
  }

  async function doUndo() {
    if (!S.project || !S.undoStack.length) return;
    S.redoStack.push(JSON.stringify({ shots: S.project.shots, timeline: S.project.timeline }));
    const prev = JSON.parse(S.undoStack.pop());
    const res = await api(`/api/v2/projects/${S.project.id}/save`, { method: "POST", body: prev });
    S.project = res.project;
    toast("Undid last edit", "ok");
    render();
  }

  async function doRedo() {
    if (!S.project || !S.redoStack.length) return;
    S.undoStack.push(JSON.stringify({ shots: S.project.shots, timeline: S.project.timeline }));
    const nxt = JSON.parse(S.redoStack.pop());
    const res = await api(`/api/v2/projects/${S.project.id}/save`, { method: "POST", body: nxt });
    S.project = res.project;
    toast("Redid edit", "ok");
    render();
  }

  function injectFontFaces(fontsList) {
    let styleEl = document.getElementById("av-custom-fonts-style");
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = "av-custom-fonts-style";
      document.head.appendChild(styleEl);
    }
    styleEl.textContent = (fontsList || []).map(f => {
      const fam = String(f.family || "").replace(/'/g, "");
      const fmt = String(f.filename || "").toLowerCase().endsWith(".otf") ? "opentype" : "truetype";
      return `@font-face { font-family: '${fam}'; src: url('${f.url}') format('${fmt}'); font-display: swap; }`;
    }).join("\n");
  }

  // ------------------------------------------------------------------ Data Loading
  async function loadBootstrap() {
    const [dash, st, projs, about] = await Promise.all([
      api("/api/v2/dashboard"),
      api("/api/v2/settings"),
      api("/api/v2/projects"),
      api("/api/v2/about"),
    ]);
    S.dashboard = dash;
    S.settings = st.settings;
    S.aiConfig = st.ai;
    S.speechModel = st.speech_model || S.speechModel;
    S.captionStyles = st.caption_styles || [];
    S.captionAnimations = st.caption_animations || [];
    S.captionLanguages = st.caption_languages || [];
    S.aiAudioReady = !!st.ai_audio_ready;
    S.fonts = st.fonts || [];
    injectFontFaces(S.fonts);
    S.viralityLabels = st.virality_labels || {};
    S.projectsList = projs.projects || [];
    S.about = about;
    if (st.settings.export_defaults) {
      S.exportOpts = { ...S.exportOpts, ...st.settings.export_defaults };
    }
    if (st.settings.reels) {
      S.ingestReelCount = Number(st.settings.reels.count || 5);
      S.ingestDurationMode = st.settings.reels.duration_mode || "auto_ai";
      S.ingestTargetDuration = Number(st.settings.reels.target_duration || 30);
      S.ingestAutoCaptions = st.settings.reels.auto_captions !== false;
    }
    if (st.settings.caption_defaults) {
      S.ingestCaptionLang = st.settings.caption_defaults.language || "auto";
    }
    if (!S.project && S.projectsList.length > 0) {
      await openProject(S.projectsList[0].id, false);
    }
    render();
    // Show first-launch onboarding ONLY once after installation
    const ob = (S.settings && S.settings.onboarding) || {};
    if (!ob.completed) {
      S.onboardingOpen = true;
      S.onboardingStep = 1;
      renderOnboardingModal();
    }
  }

  async function refreshDashboardAndProjects() {
    const [dash, projs] = await Promise.all([api("/api/v2/dashboard"), api("/api/v2/projects")]);
    S.dashboard = dash;
    S.projectsList = projs.projects || [];
  }

  async function openProject(pid, switchToEditor = true) {
    const res = await api(`/api/v2/projects/${pid}`);
    S.project = res.project;
    S.automationStatus = res.automation;
    S.selectedShotId = (S.project.shots && S.project.shots[0] && S.project.shots[0].id) || null;
    S.exportOpts.aspect = (S.project.timeline && S.project.timeline.aspect) || "16:9";
    S.exportOpts.filename = `${S.project.name.replace(/[^A-Za-z0-9._\- ]+/g, "_")}_export.mp4`;
    S.exportOpts.shot_id = S.selectedShotId || "";
    S.undoStack = [];
    S.redoStack = [];
    dirty = false;
    if (switchToEditor) S.view = "editor";
    await refreshExportEstimate();
    render();
  }

  async function refreshProject() {
    if (!S.project) return;
    const res = await api(`/api/v2/projects/${S.project.id}`);
    S.project = res.project;
    S.automationStatus = res.automation;
    if (!S.selectedShotId && S.project.shots && S.project.shots.length) {
      S.selectedShotId = S.project.shots[0].id;
    }
  }

  async function refreshExportEstimate() {
    if (!S.project || !(S.project.shots || []).length) {
      S.exportEstimate = null;
      return;
    }
    try {
      S.exportEstimate = await api(`/api/v2/projects/${S.project.id}/export/estimate`, {
        method: "POST",
        body: S.exportOpts,
      });
    } catch {
      S.exportEstimate = null;
    }
  }

  // ------------------------------------------------------------------ Polling & Autosave
  function startBackgroundTimers() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        if (S.project && S.automationStatus && (S.automationStatus.state === "running" || S.automationStatus.state === "paused")) {
          const prev = S.automationStatus.state;
          const st = await api(`/api/v2/projects/${S.project.id}/automation`);
          S.automationStatus = st;
          if (st.state === "done" || st.state === "error" || st.state === "stopped") {
            await refreshProject();
            await refreshDashboardAndProjects();
            await refreshExportEstimate();
            if (prev === "running" && st.state === "done") toast("AI analysis & automation complete", "ok");
            if (st.state === "error") toast(`Pipeline error: ${st.error}`, "error");
          }
          render();
        }
        if (S.activeIngest && ["starting", "downloading", "importing"].includes(S.activeIngest.status)) {
          const res = await api(`/api/v2/ingest/${S.activeIngest.id}`);
          S.activeIngest = res.ingest;
          if (S.activeIngest.status === "done") {
            await refreshDashboardAndProjects();
            toast(`Downloaded '${S.activeIngest.title || "video"}' — opening Studio Editor`, "ok");
            if (S.activeIngest.project_id) {
              await openProject(S.activeIngest.project_id, true);
            }
          } else if (S.activeIngest.status === "error") {
            toast(`Link download failed: ${S.activeIngest.error}`, "error");
          }
          render();
        }
        if (S.speechModel && S.speechModel.doing) {
          const sr = await api("/api/v2/speech-model/status");
          S.speechModel = sr.speech_model;
          if (S.onboardingOpen && S.onboardingStep === 3) {
            if (S.speechModel.ready) {
              advanceOnboarding(4);
            } else {
              renderOnboardingModal(true);
            }
          } else if (S.speechModalOpen) {
            renderSpeechModelModal();
          }
          if (S.speechModel.ready) {
            toast("Offline Speech-to-Text package installed!", "ok");
            const targetPid = S.speechAutoExtractProject || (S.project && S.project.id);
            S.speechAutoExtractProject = null;
            if (S.speechModalOpen) closeSpeechModelModal();
            if (targetPid && S.project && S.project.id === targetPid && (S.project.media || []).length) {
              try {
                const ar = await api(`/api/v2/projects/${targetPid}/automation/run`, {
                  method: "POST",
                  body: { trigger: "manual", tasks: ["caption_generation"] },
                });
                S.automationStatus = ar.automation;
                toast("Extracting local captions automatically...", "ok");
              } catch {
                /* pipeline may already be running */
              }
            }
            render();
          } else if (!S.speechModel.doing && S.speechModel.error) {
            toast(`Speech model download: ${S.speechModel.error}`, "error");
            render();
          }
        }
        if (S.activeExport && S.activeExport.status === "running") {
          const res = await api(`/api/v2/exports/${S.activeExport.id}`);
          S.activeExport = res.export;
          if (S.activeExport.status === "done") {
            await refreshProject();
            toast(`Export completed (${S.activeExport.actual_mb} MB)`, "ok");
          } else if (S.activeExport.status === "error") {
            toast(`Export failed: ${S.activeExport.error}`, "error");
          }
          render();
        }
      } catch {
        /* transient poll error ignored */
      }
    }, 1000);

    if (autosaveTimer) clearInterval(autosaveTimer);
    autosaveTimer = setInterval(async () => {
      if (S.project && dirty) {
        try {
          await api(`/api/v2/projects/${S.project.id}/autosave`, {
            method: "POST",
            body: { timeline: S.project.timeline, shots: S.project.shots },
          });
          dirty = false;
        } catch {
          /* ignore */
        }
      }
    }, 15000);
  }

  // ------------------------------------------------------------------ First-Launch 4-Step Swipe-Up Onboarding
  function advanceOnboarding(nextStep) {
    const card = document.getElementById("ob-active-card");
    if (card) {
      card.classList.add("swiping-out");
      setTimeout(() => {
        S.onboardingStep = nextStep;
        renderOnboardingModal(false);
      }, 240);
    } else {
      S.onboardingStep = nextStep;
      renderOnboardingModal(false);
    }
  }

  async function finishOnboarding() {
    try {
      const res = await api("/api/v2/settings", {
        method: "PUT",
        body: { onboarding: { completed: true } },
      });
      S.settings = res.settings;
    } catch {
      /* never block entering studio */
    }
    S.onboardingOpen = false;
    const host = document.getElementById("modal-host");
    if (host) host.innerHTML = "";
    render();
  }

  function renderOnboardingModal(inPlaceUpdate = false) {
    const host = document.getElementById("modal-host");
    if (!host || !S.onboardingOpen) return;

    const step = S.onboardingStep;
    const sm = S.speechModel || {};
    const dots = [1, 2, 3, 4].map(i =>
      `<span class="ob-dot ${i === step ? "active" : i < step ? "done" : ""}"></span>`
    ).join("");

    const igSvg = `
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
        <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
        <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>
      </svg>
    `;

    let cardContent = "";
    if (step === 1) {
      cardContent = `
        <div class="row-between">
          <div class="row" style="gap:9px">
            <img src="/brand/favicon.svg" alt="AgentVid" style="width:30px;height:30px;border-radius:8px" />
            <span style="font-weight:750;letter-spacing:0.14em;font-size:12px">AGENTVID STUDIO</span>
          </div>
          <img src="/brand/creative-creature-logo.png" alt="Creative Creature" style="height:22px;width:auto" />
        </div>

        <div style="text-align:center;margin-top:4px">
          <div class="submit-eyebrow" style="margin-bottom:12px"><span class="submit-eyebrow-dot"></span> Free Creator Edition</div>
          <h2 style="margin:0;font-size:21px;font-weight:720;letter-spacing:-0.03em;color:#ffffff">We're giving AgentVid away for free</h2>
          <p class="muted" style="margin:8px 0 0;font-size:12.5px;line-height:1.55">
            No subscriptions, no watermarks, no locked exports. Follow
            <strong style="color:#ffffff">Creative Creature</strong> on Instagram for drops and new tools.
          </p>
        </div>

        <div class="ob-ig-showcase">
          <div class="ob-ig-badge">${igSvg}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:15px;font-weight:750;color:#ffffff">@we.arecc</div>
            <div class="muted" style="font-size:11.5px">Creative Creature · AI tools, film &amp; visual drops</div>
          </div>
          <button class="btn btn-sm ${S.onboardingIgFollowed ? "btn-primary" : ""}" id="ob-ig-follow">
            ${S.onboardingIgFollowed ? `${svg("check", 12)} Opened` : `${svg("external", 12)} Follow`}
          </button>
        </div>

        <div class="row-between" style="margin-top:4px">
          <span class="muted" style="font-size:11px">Step 1 of 4</span>
          <button class="btn-white-cta" id="ob-next-1" style="padding:9px 20px">
            Next ${svg("arrowRight", 15)}
          </button>
        </div>
      `;
    } else if (step === 2) {
      cardContent = `
        <div class="row-between">
          <span class="badge score-strong">Creative Creature Insider</span>
          <img src="/brand/creative-creature-logo.png" alt="Creative Creature" style="height:20px;width:auto" />
        </div>

        <div>
          <h2 style="margin:0;font-size:20px;font-weight:750;letter-spacing:-0.02em">Get our next free creator tools first</h2>
          <p class="muted" style="margin:6px 0 0;font-size:12.5px;line-height:1.55">
            Drop your email below and we'll update you whenever we release more amazing free AI software, presets, and studio updates.
          </p>
        </div>

        <form id="ob-newsletter-form" style="display:flex;flex-direction:column;gap:10px">
          <div class="submit-url-box" style="padding:4px 12px">
            <input id="ob-email-inp" type="email" required placeholder="you@example.com" value="${esc(S.onboardingEmail || "")}" ${S.onboardingEmailBusy ? "disabled" : ""} />
          </div>
          ${S.onboardingEmailError ? `<div style="font-size:12px;color:var(--rose)">${esc(S.onboardingEmailError)}</div>` : ""}
          ${S.onboardingEmailStatus ? `<div style="font-size:12px;color:var(--emerald)">${esc(S.onboardingEmailStatus)}</div>` : ""}
          <div class="row-between" style="margin-top:4px">
            <button type="button" class="btn btn-sm" id="ob-skip-2" ${S.onboardingEmailBusy ? "disabled" : ""}>Skip for now</button>
            <button type="submit" class="btn-white-cta" style="padding:9px 18px" ${S.onboardingEmailBusy ? "disabled" : ""}>
              ${S.onboardingEmailBusy ? `${svg("loader", 14, "spin")} Subscribing...` : `Subscribe &amp; Next ${svg("arrowRight", 15)}`}
            </button>
          </div>
        </form>
      `;
    } else if (step === 3) {
      const pct = sm.ready ? 100 : (sm.percent || 0);
      const circ = 2 * Math.PI * 44;
      const offset = circ * (1 - pct / 100);
      const activeDownloads = sm.doing ? 1 : 0;
      const stageDesc = sm.ready
        ? "Offline speech package installed!"
        : sm.stage === "extracting"
          ? `Extracting neural model files (${sm.items_done || 0} / ${sm.items_total || 4} files)...`
          : sm.stage === "downloading"
            ? `Active download (${activeDownloads} package) · ${sm.downloaded_mb || 0} MB / ${sm.total_mb || 480} MB`
            : "Ready to download 1 offline speech package (~480 MB)";

      cardContent = `
        <div class="row-between">
          <span class="badge score-high">Offline Auto-Captions</span>
          <span class="badge">No API Key Required</span>
        </div>

        <div style="text-align:center">
          <h2 style="margin:0;font-size:19.5px;font-weight:750;letter-spacing:-0.02em">Download Offline Auto-Captions Package</h2>
          <p class="muted" style="margin:6px 0 0;font-size:12.5px;line-height:1.5">
            One-time local download so videos imported from your PC get automatic word-by-word captions completely offline.
          </p>
        </div>

        <div class="ob-dl-ring-wrap">
          <svg width="112" height="112" viewBox="0 0 112 112">
            <defs>
              <linearGradient id="obRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#0066ff"/>
                <stop offset="100%" stop-color="#60a5fa"/>
              </linearGradient>
            </defs>
            <circle cx="56" cy="56" r="44" fill="none" stroke="rgba(255,255,255,0.09)" stroke-width="7"/>
            <circle cx="56" cy="56" r="44" fill="none" stroke="url(#obRingGrad)" stroke-width="7" stroke-linecap="round"
              stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}" style="transition:stroke-dashoffset 0.3s ease"/>
          </svg>
          <div class="ob-dl-pct">
            <span>${pct}%</span>
            <span style="font-size:9.5px;color:var(--text-2);font-weight:500">${sm.doing ? `${activeDownloads} active` : sm.ready ? "READY" : "~480 MB"}</span>
          </div>
        </div>

        <div>
          <div class="row-between" style="font-size:11.5px;margin-bottom:5px">
            <span style="color:${sm.error && !sm.doing ? "var(--rose)" : "var(--cyan)"}">${esc(sm.error && !sm.doing ? sm.error : stageDesc)}</span>
            <span class="mono">${sm.downloaded_mb || 0} / ${sm.total_mb || 480} MB</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
        </div>

        <div class="row-between wrap" style="gap:8px;margin-top:4px">
          ${sm.doing ? `
            <button class="btn btn-danger btn-sm" id="ob-dl-cancel">Cancel</button>
            <button class="btn btn-sm" id="ob-dl-continue-bg">Continue while downloading →</button>
          ` : sm.ready ? `
            <span class="muted" style="font-size:11.5px">Package verified on disk.</span>
            <button class="btn-white-cta" id="ob-to-done" style="padding:9px 18px">Finish ${svg("arrowRight", 15)}</button>
          ` : `
            <button class="btn btn-sm" id="ob-skip-3">Skip for now</button>
            <button class="btn-white-cta" id="ob-dl-start" style="padding:9px 18px">
              ${svg("download", 14)} Download Package
            </button>
          `}
        </div>
      `;
    } else {
      cardContent = `
        <div style="text-align:center;padding:8px 4px">
          <div class="ob-tick-wrap">
            <svg width="64" height="64" viewBox="0 0 80 80" fill="none">
              <circle class="ob-tick-circle" cx="40" cy="40" r="34" stroke="#0066ff" stroke-width="4.5" stroke-linecap="round"/>
              <path class="ob-tick-check" d="M24 41.5L35 52.5L57 29.5" stroke="#ffffff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <h2 style="margin:14px 0 8px;font-size:21px;font-weight:750;letter-spacing:-0.02em;color:#ffffff">
            Now you can totally use this software for free.
          </h2>
          <p class="muted" style="margin:0 0 18px;font-size:13px;line-height:1.55">
            AgentVid Studio is unlocked and ready locally on your PC — paste any YouTube link or import a local video to start creating.
          </p>
          <div style="display:flex;justify-content:center;margin-bottom:14px">
            <img src="/brand/creative-creature-logo.png" alt="Creative Creature" style="height:26px;width:auto" />
          </div>
          <button class="btn-white-cta" id="ob-finish-btn" style="width:100%;padding:12px 20px;font-size:13.5px">
            Launch AgentVid Studio ${svg("arrowRight", 15)}
          </button>
        </div>
      `;
    }

    if (inPlaceUpdate && document.getElementById("ob-active-card")) {
      document.getElementById("ob-active-card").innerHTML = cardContent + `<div class="ob-dots">${dots}</div>`;
    } else {
      host.innerHTML = `
        <div class="ob-backdrop">
          <div class="ob-deck">
            <div class="ob-aura"></div>
            <div class="ob-card" id="ob-active-card">
              ${cardContent}
              <div class="ob-dots">${dots}</div>
            </div>
          </div>
        </div>
      `;
    }

    // Bind active step events
    if (step === 1) {
      const igBtn = document.getElementById("ob-ig-follow");
      if (igBtn) {
        igBtn.onclick = async () => {
          S.onboardingIgFollowed = true;
          const url = "https://www.instagram.com/we.arecc/";
          if (window.agentvidDesktop && window.agentvidDesktop.openExternal) {
            window.agentvidDesktop.openExternal(url);
          } else {
            window.open(url, "_blank", "noopener,noreferrer");
          }
          api("/api/v2/settings", { method: "PUT", body: { onboarding: { instagram_clicked: true } } }).catch(() => {});
          renderOnboardingModal(true);
        };
      }
      const next1 = document.getElementById("ob-next-1");
      if (next1) next1.onclick = () => advanceOnboarding(2);
    } else if (step === 2) {
      const form = document.getElementById("ob-newsletter-form");
      const inp = document.getElementById("ob-email-inp");
      if (inp) inp.oninput = () => { S.onboardingEmail = inp.value; };
      if (form) {
        form.onsubmit = async e => {
          e.preventDefault();
          S.onboardingEmail = (inp ? inp.value : "").trim();
          S.onboardingEmailBusy = true;
          S.onboardingEmailError = "";
          S.onboardingEmailStatus = "";
          renderOnboardingModal(true);
          try {
            const resp = await fetch("/api/newsletter", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ email: S.onboardingEmail }),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) {
              S.onboardingEmailError = data.error || data.detail || "Could not subscribe. Check your email or try again.";
              S.onboardingEmailBusy = false;
              renderOnboardingModal(true);
              return;
            }
            S.onboardingEmailBusy = false;
            S.onboardingEmailStatus = data.message || "Subscribed successfully!";
            renderOnboardingModal(true);
            setTimeout(() => advanceOnboarding(S.speechModel.ready ? 4 : 3), 650);
          } catch {
            S.onboardingEmailBusy = false;
            S.onboardingEmailError = "Network unavailable right now. You can skip and continue using AgentVid offline.";
            renderOnboardingModal(true);
          }
        };
      }
      const skip2 = document.getElementById("ob-skip-2");
      if (skip2) skip2.onclick = () => advanceOnboarding(S.speechModel.ready ? 4 : 3);
    } else if (step === 3) {
      const startBtn = document.getElementById("ob-dl-start");
      if (startBtn) {
        startBtn.onclick = async () => {
          try {
            const res = await api("/api/v2/speech-model/download", { method: "POST" });
            S.speechModel = res.speech_model;
            renderOnboardingModal(true);
          } catch (err) {
            toast(err.message, "error");
          }
        };
      }
      const cancelBtn = document.getElementById("ob-dl-cancel");
      if (cancelBtn) {
        cancelBtn.onclick = async () => {
          const res = await api("/api/v2/speech-model/cancel", { method: "POST" });
          S.speechModel = res.speech_model;
          renderOnboardingModal(true);
        };
      }
      const skip3 = document.getElementById("ob-skip-3");
      if (skip3) skip3.onclick = () => advanceOnboarding(4);
      const contBg = document.getElementById("ob-dl-continue-bg");
      if (contBg) contBg.onclick = () => advanceOnboarding(4);
      const toDone = document.getElementById("ob-to-done");
      if (toDone) toDone.onclick = () => advanceOnboarding(4);
    } else if (step === 4) {
      const fin = document.getElementById("ob-finish-btn");
      if (fin) fin.onclick = finishOnboarding;
    }
  }

  function closeSpeechModelModal(dismissForSession = false) {
    S.speechModalOpen = false;
    if (dismissForSession) S.speechPromptDismissed = true;
    const host = document.getElementById("modal-host");
    if (host) host.innerHTML = "";
  }

  function renderSpeechModelModal() {
    const host = document.getElementById("modal-host");
    if (!host || !S.speechModalOpen) return;
    const sm = S.speechModel || {};
    const busy = !!sm.doing;
    const stageText = sm.stage === "extracting"
      ? "Extracting offline speech model files..."
      : sm.stage === "downloading"
        ? `Downloading offline speech package (${sm.downloaded_mb || 0} / ${sm.total_mb || 480} MB)...`
        : sm.stage === "ready"
          ? "Offline speech package installed and ready!"
          : sm.error || "";

    host.innerHTML = `
      <div class="modal-backdrop" id="av-speech-modal-bg">
        <div class="modal-card" style="width:min(510px,94vw);border-color:rgba(56,189,248,0.4)">
          <div class="row-between" style="margin-bottom:10px">
            <div class="row" style="gap:9px">
              <span style="width:32px;height:32px;border-radius:9px;background:rgba(56,189,248,0.16);border:1px solid rgba(56,189,248,0.4);display:grid;place-items:center;color:var(--cyan)">${svg("type", 16)}</span>
              <div>
                <strong style="font-size:15px;display:block">Offline Auto-Captions Package</strong>
                <span class="muted" style="font-size:11px">For local video files imported from your PC</span>
              </div>
            </div>
            ${busy ? "" : `<button class="btn btn-icon btn-sm" id="av-speech-close">${svg("x", 14)}</button>`}
          </div>

          <div class="row wrap" style="gap:6px;margin-bottom:12px">
            <span class="badge score-high">100% Free &amp; Offline</span>
            <span class="badge score-strong">No API Key Needed</span>
            <span class="badge">One-Time Download (~480 MB)</span>
          </div>

          <p style="font-size:12.5px;color:var(--text-1);margin:0 0 14px;line-height:1.55">
            Local video files don't carry YouTube captions. Download the offline speech-to-text package once so
            AgentVid can automatically transcribe spoken audio into word-by-word kinetic captions right on this PC.
          </p>

          ${busy || sm.error ? `
            <div style="margin-bottom:14px;padding:12px;border-radius:10px;background:rgba(8,10,16,0.85);border:1px solid var(--border)">
              <div class="row-between" style="margin-bottom:6px;font-size:12px">
                <span style="color:${sm.error && !busy ? "var(--rose)" : "var(--cyan)"}">${esc(stageText)}</span>
                <span class="mono">${sm.percent || 0}%</span>
              </div>
              <div class="progress-bar"><div class="progress-fill" style="width:${sm.percent || 0}%"></div></div>
            </div>
          ` : ""}

          <div class="row-between wrap" style="gap:10px;margin-top:8px">
            ${busy ? `
              <button class="btn btn-danger btn-sm" id="av-speech-cancel">Cancel Download</button>
              <span class="muted" style="font-size:11px">You can keep editing — captions extract automatically when done.</span>
            ` : `
              <button class="btn btn-sm" id="av-speech-later">Not Now (Edit Captions Manually)</button>
              <button class="btn-white-cta" style="padding:8px 16px;font-size:12.5px" id="av-speech-start">
                ${svg("download", 14)} Download Package (~480 MB)
              </button>
            `}
          </div>
        </div>
      </div>
    `;

    const closeBtn = document.getElementById("av-speech-close");
    if (closeBtn) closeBtn.onclick = () => closeSpeechModelModal(true);
    const laterBtn = document.getElementById("av-speech-later");
    if (laterBtn) laterBtn.onclick = () => closeSpeechModelModal(true);
    const bg = document.getElementById("av-speech-modal-bg");
    if (bg && !busy) bg.onclick = e => { if (e.target.id === "av-speech-modal-bg") closeSpeechModelModal(true); };

    const startBtn = document.getElementById("av-speech-start");
    if (startBtn) {
      startBtn.onclick = async () => {
        try {
          const res = await api("/api/v2/speech-model/download", { method: "POST" });
          S.speechModel = res.speech_model;
          renderSpeechModelModal();
          render();
        } catch (err) {
          toast(err.message, "error");
        }
      };
    }

    const cancelBtn = document.getElementById("av-speech-cancel");
    if (cancelBtn) {
      cancelBtn.onclick = async () => {
        try {
          const res = await api("/api/v2/speech-model/cancel", { method: "POST" });
          S.speechModel = res.speech_model;
          renderSpeechModelModal();
        } catch (err) {
          toast(err.message, "error");
        }
      };
    }
  }

  function openSpeechModelModal(projectIdForAutoExtract = null) {
    S.speechAutoExtractProject = projectIdForAutoExtract || (S.project && S.project.id) || null;
    S.speechModalOpen = true;
    renderSpeechModelModal();
  }

  // ------------------------------------------------------------------ Media Import (Native Desktop or File Input)
  async function triggerMediaImport(kind = "video", createIfMissing = false) {
    if (!S.project) {
      if (!createIfMissing) {
        toast("Create or open a project first.", "error");
        return;
      }
      const created = await api("/api/v2/projects", { method: "POST", body: { name: "New Studio Project" } });
      await openProject(created.project.id, true);
      await refreshDashboardAndProjects();
    }

    // Prefer native Electron file picker for instant local import (zero RAM bloat on huge videos!)
    if (window.agentvidDesktop && window.agentvidDesktop.pickMediaFile) {
      const picked = await window.agentvidDesktop.pickMediaFile(kind);
      if (!picked) return;
      toast(`Importing ${kind}...`);
      const res = await api(`/api/v2/projects/${S.project.id}/media/import-local`, {
        method: "POST",
        body: { path: picked, kind, trigger_auto: true },
      });
      S.project = res.project;
      S.automationStatus = res.automation;
      await refreshDashboardAndProjects();
      toast(
        kind === "video"
          ? (S.settings.auto_mode ? "Video imported — AUTO mode pipeline started" : "Video imported (MANUAL mode)")
          : "Background audio imported",
        "ok"
      );
      S.view = "editor";
      render();
      if (kind === "video" && !S.speechModel.ready && !S.speechPromptDismissed && S.settings.automation && S.settings.automation.caption_generation !== false) {
        openSpeechModelModal(S.project.id);
      }
      return;
    }

    const input = document.getElementById(kind === "audio" ? "hidden-audio-input" : "hidden-video-input");
    input.value = "";
    input.onchange = async () => {
      const f = input.files && input.files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append("file", f);
      fd.append("kind", kind);
      fd.append("trigger_auto", "true");
      toast(`Uploading ${f.name}...`);
      try {
        const res = await api(`/api/v2/projects/${S.project.id}/media/upload`, { method: "POST", body: fd });
        S.project = res.project;
        S.automationStatus = res.automation;
        await refreshDashboardAndProjects();
        toast(S.settings.auto_mode ? "Imported — AUTO pipeline running" : "Imported in MANUAL mode", "ok");
        S.view = "editor";
        render();
        if (kind === "video" && !S.speechModel.ready && !S.speechPromptDismissed && S.settings.automation && S.settings.automation.caption_generation !== false) {
          openSpeechModelModal(S.project.id);
        }
      } catch (err) {
        toast(err.message, "error");
      }
    };
    input.click();
  }

  function computeLiveCropRect(vid, curShot) {
    const aspect = (S.project && S.project.timeline && S.project.timeline.aspect) || "9:16";
    const activeMedia = (S.project && S.project.media || []).find(m => m.id === S.project.active_media_id)
      || (S.project && S.project.media || [])[0] || {};
    const srcW = (vid && vid.videoWidth) || Number(activeMedia.width || 1920);
    const srcH = (vid && vid.videoHeight) || Number(activeMedia.height || 1080);
    const targetMap = { "9:16": 9 / 16, "1:1": 1.0, "16:9": 16 / 9 };
    const targetRatio = targetMap[aspect] || (9 / 16);
    const srcRatio = srcW / Math.max(1, srcH);

    let baseW = 1.0, baseH = 1.0;
    if (srcRatio > targetRatio) {
      baseH = 1.0;
      baseW = Math.min(1.0, targetRatio / srcRatio);
    } else {
      baseW = 1.0;
      baseH = Math.min(1.0, srcRatio / targetRatio);
    }
    const ft = (S.project && S.project.face_tracking) || {};
    const ed = (curShot && curShot.edit) || {};
    const zoom = Math.max(1.0, Math.min(2.5, Number(ed.zoom || 1.0)));
    let panX = Math.max(0, Math.min(1, Number(ed.pan_x ?? 0.5)));
    let panY = Math.max(0, Math.min(1, Number(ed.pan_y ?? 0.5)));
    const rf = (curShot && curShot.suggestions && curShot.suggestions.reframing && curShot.suggestions.reframing[aspect])
      || (ft.reframing_suggestions && ft.reframing_suggestions[aspect]);
    if ((ed.crop_mode || "auto") !== "manual" && (aspect === "9:16" || aspect === "1:1") && rf) {
      panX = Math.max(0, Math.min(1, Number(rf.pan_x ?? panX)));
      panY = Math.max(0, Math.min(1, Number(rf.pan_y ?? panY)));
    }
    const w = Math.max(0.08, Math.min(1.0, baseW / zoom));
    const h = Math.max(0.08, Math.min(1.0, baseH / zoom));
    const x = Math.max(0, Math.min(1.0 - w, panX - w / 2));
    const y = Math.max(0, Math.min(1.0 - h, panY - h / 2));
    return { aspect, x, y, w, h, isFull: w >= 0.985 && h >= 0.985 };
  }

  // ------------------------------------------------------------------ Live Video Preview + Face & Caption Overlays
  function syncVideoOverlays() {
    const vid = document.getElementById("studio-video");
    const layer = document.getElementById("video-overlay-layer");
    const capEl = document.getElementById("live-caption-overlay");
    const tcEl = document.getElementById("transport-timecode");
    if (!vid || !S.project) return;

    const t = vid.currentTime || 0;
    const dur = vid.duration || 0;
    if (tcEl) tcEl.textContent = `${fmtTime(t)} / ${fmtTime(dur)}`;

    if (S.playingShotEnd !== null && t >= S.playingShotEnd) {
      vid.pause();
      S.playingShotEnd = null;
      const btn = document.getElementById("btn-play-toggle");
      if (btn) btn.innerHTML = `${svg("play", 13)} Play`;
    }

    // Apply live zoom/pan preview for current shot
    const shots = S.project.shots || [];
    const curShot = shots.find(s => t >= s.trim_start && t <= s.trim_end) || shots.find(s => s.id === S.selectedShotId);
    if (curShot && curShot.edit) {
      const z = Number(curShot.edit.zoom || 1.0);
      const px = (0.5 - Number(curShot.edit.pan_x ?? 0.5)) * 100 * (z - 1);
      const py = (0.5 - Number(curShot.edit.pan_y ?? 0.5)) * 100 * (z - 1);
      vid.style.transform = z > 1.01 ? `scale(${z}) translate(${px}%, ${py}%)` : "";
      vid.playbackRate = Math.max(0.25, Math.min(4.0, Number(curShot.edit.speed || 1.0)));
    }

    // Face Tracking Bounding Boxes + Smart Reframe Guide
    if (layer) {
      let html = "";
      const ft = S.project.face_tracking || {};
      if (S.showFaceOverlay && (ft.frame_samples || []).length) {
        let nearest = ft.frame_samples[0];
        let bestD = Infinity;
        for (const smp of ft.frame_samples) {
          const d = Math.abs(smp.t - t);
          if (d < bestD) { bestD = d; nearest = smp; }
        }
        if (nearest && bestD <= 1.8) {
          for (const f of nearest.faces || []) {
            const isPrim = ft.primary_subject_id === f.subject_id;
            html += `
              <div class="face-box ${isPrim ? "primary" : ""}" style="left:${f.x * 100}%;top:${f.y * 100}%;width:${f.w * 100}%;height:${f.h * 100}%">
                <div class="face-box-label">Subject ${f.subject_id} · ${Math.round(f.confidence * 100)}%${f.closeup ? " · CU" : ""}</div>
              </div>
            `;
          }
        }
      }
      const cropRect = computeLiveCropRect(vid, curShot);
      if (S.showReframeGuide) {
        const keptPct = Math.round(cropRect.w * cropRect.h * 100);
        const tagText = cropRect.isFull ? `${cropRect.aspect} FULL FRAME` : `${cropRect.aspect} CROP · ${keptPct}% KEPT`;

        html += `
          <div class="reframe-guide ${cropRect.isFull ? "is-full" : ""}" style="left:${(cropRect.x * 100).toFixed(2)}%;top:${(cropRect.y * 100).toFixed(2)}%;width:${(cropRect.w * 100).toFixed(2)}%;height:${(cropRect.h * 100).toFixed(2)}%">
            <div class="rg-grid"></div>
            <span class="rg-corner tl"></span>
            <span class="rg-corner tr"></span>
            <span class="rg-corner bl"></span>
            <span class="rg-corner br"></span>
            <div class="rg-tag">${esc(tagText)}</div>
          </div>
        `;
      }
      layer.innerHTML = html;
    }

    // Live Synchronized Caption Preview (aligned inside active crop frame + draggable X/Y)
    if (capEl) {
      const tl = S.project.timeline || {};
      const cfg = tl.caption_config || {};
      const cues = tl.captions || [];
      const capOn = cfg.enabled !== false;
      const activeCue = capOn ? cues.find(c => t >= c.start && t <= c.end) : null;
      const shotOverlay = curShot && curShot.edit && curShot.edit.text_overlay;
      const cropRect = computeLiveCropRect(vid, curShot);
      const xPct = Math.round(Number(cfg.x_offset ?? 50));
      const yPct = Math.round(Number(cfg.y_offset ?? 80));
      const fSize = Math.max(12, Math.round((Number(cfg.font_size || 64)) * 0.34));
      if (!capEl.classList.contains("is-dragging")) {
        const visLeft = (cropRect.x + cropRect.w * (xPct / 100)) * 100;
        const visTop = (cropRect.y + cropRect.h * (yPct / 100)) * 100;
        capEl.style.left = `${visLeft.toFixed(2)}%`;
        capEl.style.top = `${visTop.toFixed(2)}%`;
        capEl.style.maxWidth = `${Math.max(26, Math.round(cropRect.w * 88))}%`;
        capEl.style.fontSize = `${fSize}px`;
        capEl.setAttribute("data-drag-hint", `Drag X/Y · ${xPct}% / ${yPct}%`);
      }
      if (activeCue) {
        capEl.style.display = "block";
        capEl.textContent = cfg.uppercase ? String(activeCue.text || "").toUpperCase() : activeCue.text;
      } else if (capOn && vid.paused) {
        const shotCue = curShot
          ? cues.find(c => c.start >= (curShot.trim_start || 0) - 0.5 && c.start <= (curShot.trim_end || 999999))
          : cues[0];
        const previewTxt = (shotCue && shotCue.text) || (curShot && curShot.hook) || "AUTO-CAPTIONS ON · DRAG TO MOVE";
        capEl.style.display = "block";
        capEl.textContent = cfg.uppercase ? String(previewTxt).toUpperCase() : previewTxt;
      } else if (shotOverlay) {
        capEl.style.display = "block";
        capEl.textContent = shotOverlay;
      } else {
        capEl.style.display = "none";
      }
    }
  }

  function bindVideoEvents() {
    const vid = document.getElementById("studio-video");
    if (!vid) return;
    vid.ontimeupdate = syncVideoOverlays;
    vid.onloadedmetadata = syncVideoOverlays;
    vid.onplay = () => {
      const btn = document.getElementById("btn-play-toggle");
      if (btn) btn.innerHTML = `${svg("pause", 13)} Pause`;
      syncVideoOverlays();
    };
    vid.onpause = () => {
      const btn = document.getElementById("btn-play-toggle");
      if (btn) btn.innerHTML = `${svg("play", 13)} Play`;
      syncVideoOverlays();
    };

    // Direct 2D drag-to-move (horizontal X + vertical Y) caption positioning on the Program Monitor
    const capEl = document.getElementById("live-caption-overlay");
    const frameWrap = document.getElementById("video-frame-wrap");
    if (capEl && frameWrap && !capEl.dataset.dragBound) {
      capEl.dataset.dragBound = "1";
      capEl.addEventListener("mousedown", ev => {
        if (!S.project) return;
        ev.preventDefault();
        ev.stopPropagation();
        capEl.classList.add("is-dragging");
        const curCfg = (S.project.timeline || {}).caption_config || {};
        let lastX = Math.round(Number(curCfg.x_offset ?? 50));
        let lastY = Math.round(Number(curCfg.y_offset ?? 80));

        const onMove = mv => {
          const rect = frameWrap.getBoundingClientRect();
          if (rect.width <= 0 || rect.height <= 0) return;
          const shots = (S.project && S.project.shots) || [];
          const curShot = shots.find(s => s.id === S.selectedShotId) || shots[0] || null;
          const cr = computeLiveCropRect(vid, curShot);
          const cropLeftPx = rect.left + rect.width * cr.x;
          const cropTopPx = rect.top + rect.height * cr.y;
          const cropW = Math.max(1, rect.width * cr.w);
          const cropH = Math.max(1, rect.height * cr.h);
          const rawX = ((mv.clientX - cropLeftPx) / cropW) * 100;
          const rawY = ((mv.clientY - cropTopPx) / cropH) * 100;
          lastX = Math.max(10, Math.min(90, Math.round(rawX)));
          lastY = Math.max(10, Math.min(90, Math.round(rawY)));
          capEl.style.left = `${((cr.x + cr.w * (lastX / 100)) * 100).toFixed(2)}%`;
          capEl.style.top = `${((cr.y + cr.h * (lastY / 100)) * 100).toFixed(2)}%`;
          capEl.setAttribute("data-drag-hint", `X: ${lastX}% · Y: ${lastY}%`);
          const xLbl = document.getElementById("editor-cap-x-label");
          if (xLbl) xLbl.textContent = `${lastX}%`;
          const xSld = document.getElementById("editor-cap-x-slider");
          if (xSld) {
            xSld.value = String(lastX);
            xSld.style.setProperty("--pct", `${((lastX - 10) / 80) * 100}%`);
          }
          const yLbl = document.getElementById("editor-cap-y-label");
          if (yLbl) yLbl.textContent = `${lastY}%`;
          const ySld = document.getElementById("editor-cap-y-slider");
          if (ySld) {
            ySld.value = String(lastY);
            ySld.style.setProperty("--pct", `${((lastY - 10) / 80) * 100}%`);
          }
        };

        const onUp = async () => {
          window.removeEventListener("mousemove", onMove);
          window.removeEventListener("mouseup", onUp);
          capEl.classList.remove("is-dragging");
          capEl.setAttribute("data-drag-hint", `Drag X/Y · ${lastX}% / ${lastY}%`);
          const pos = lastY < 33 ? "top" : lastY > 66 ? "bottom" : "center";
          try {
            pushUndoSnapshot();
            const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
              method: "PUT",
              body: { caption_config: { x_offset: lastX, y_offset: lastY, position: pos } },
            });
            S.project = res.project;
            toast(`Caption position saved (X: ${lastX}%, Y: ${lastY}%)`, "ok");
            render();
            syncVideoOverlays();
          } catch (err) {
            toast(err.message || "Could not save caption position", "error");
          }
        };

        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
      });
    }
    syncVideoOverlays();
  }

  // ------------------------------------------------------------------ Shell Renderer
  function render() {
    const root = document.getElementById("app");
    if (!root) return;

    // Preserve video playback time across re-renders if staying in editor
    const existingVid = document.getElementById("studio-video");
    const savedTime = existingVid ? existingVid.currentTime : null;
    const savedSrc = existingVid ? existingVid.getAttribute("src") : null;

    const autoOn = !!(S.settings && S.settings.auto_mode);
    const run = S.automationStatus;
    const isRunning = run && (run.state === "running" || run.state === "paused");

    const groups = ["Studio", "Workspace", "Intelligence", "Delivery", "System"];
    const navHtml = groups.map(g => {
      const items = NAV_ITEMS.filter(n => n.group === g);
      return `
        <div class="nav-section-label">${g}</div>
        ${items.map(item => {
          let badge = "";
          if (item.id === "shots" && S.project) badge = `<span class="nav-badge">${(S.project.shots || []).length}</span>`;
          if (item.id === "virality" && S.project && S.project.virality && S.project.virality.overall_score) {
            badge = `<span class="nav-badge">${S.project.virality.overall_score}</span>`;
          }
          return `
            <button class="nav-item ${S.view === item.id ? "active" : ""}" data-nav="${item.id}">
              ${svg(item.icon, 15)}
              <span>${item.label}</span>
              ${badge}
            </button>
          `;
        }).join("")}
      `;
    }).join("");

    let bodyHtml = "";
    if (S.view === "submit") bodyHtml = Views.renderSubmitVideo(S);
    else if (S.view === "home") bodyHtml = Views.renderHome(S);
    else if (S.view === "projects") bodyHtml = Views.renderProjects(S);
    else if (S.view === "editor") bodyHtml = Views.renderEditor(S);
    else if (S.view === "analysis") bodyHtml = Views.renderAnalysis(S);
    else if (S.view === "shots") bodyHtml = Views.renderShotLibrary(S);
    else if (S.view === "virality") bodyHtml = Views.renderVirality(S);
    else if (S.view === "captions") bodyHtml = Views.renderCaptions(S);
    else if (S.view === "export") bodyHtml = Views.renderExport(S);
    else if (S.view === "settings") bodyHtml = Views.renderSettings(S);

    root.innerHTML = `
      <header class="topbar">
        <div class="topbar-left">
          <div class="brand-lockup">
            <img class="brand-mark" src="/brand/favicon.svg" alt="AgentVid" />
            <div>
              <div class="brand-title">AGENTVID<span class="brand-dot"></span></div>
              <div class="brand-sub">Studio</div>
            </div>
          </div>
          <div class="project-pill" data-nav="projects" title="Switch Project">
            ${svg("folder", 13)}
            <span>${esc(S.project ? S.project.name : "No Project Selected")}</span>
          </div>
        </div>

        <div class="topbar-center">
          <button class="auto-pill ${autoOn ? "is-auto" : ""}" data-act="toggle-auto-mode" title="Toggle AUTO / MANUAL Automation Mode">
            <span class="auto-track"><span class="auto-knob"></span></span>
            <span class="auto-label">${autoOn ? "AUTO ON" : "MANUAL"}</span>
            <span class="auto-mode-tag">${autoOn ? "AI" : "OFF"}</span>
          </button>
          ${isRunning ? `
            <div class="auto-status-chip">
              ${svg("loader", 12, run.state === "running" ? "spin" : "")}
              <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(run.operation || run.state)} (${Math.round((run.progress || 0) * 100)}%)</span>
              ${run.state === "running"
                ? `<button class="btn btn-sm" style="padding:1px 5px;font-size:10px" data-act="auto-pause">Pause</button>`
                : `<button class="btn btn-sm" style="padding:1px 5px;font-size:10px" data-act="auto-resume">Resume</button>`}
              <button class="btn btn-sm btn-danger" style="padding:1px 5px;font-size:10px" data-act="auto-stop">Stop</button>
            </div>
          ` : ""}
        </div>

        <div class="topbar-right">
          <button class="btn btn-sm btn-icon" data-act="undo" title="Undo" ${S.undoStack.length ? "" : "disabled"}>${svg("undo", 14)}</button>
          <button class="btn btn-sm btn-icon" data-act="redo" title="Redo" ${S.redoStack.length ? "" : "disabled"}>${svg("redo", 14)}</button>
          <button class="btn btn-sm" data-act="save-project" ${S.project ? "" : "disabled"}>${svg("save", 13)} Save</button>
          <button class="btn btn-sm btn-primary" data-nav="export" ${S.project ? "" : "disabled"}>${svg("download", 13)} Export</button>
          ${window.agentvidDesktop ? `
            <div class="win-controls">
              <button class="win-btn" data-win="minimize" title="Minimize">${svg("minus", 13)}</button>
              <button class="win-btn" data-win="maximize" title="Maximize">${svg("maximize", 12)}</button>
              <button class="win-btn close" data-win="close" title="Close">${svg("x", 14)}</button>
            </div>
          ` : ""}
        </div>
      </header>

      <aside class="sidebar">
        <div class="nav-list">${navHtml}</div>
        <div class="sidebar-footer">
          <img class="cc-logo-sidebar" src="/brand/creative-creature-logo.png" alt="Creative Creature" />
          <div class="studio-credit">
            WE.ARECC · By <strong>i.sayak007</strong>
          </div>
        </div>
      </aside>

      <main class="main-view">${bodyHtml}</main>
    `;

    bindVideoEvents();
    if (window.AVControls) {
      window.AVControls.enhance(root);
    }
    if (savedTime !== null && S.view === "editor") {
      const nv = document.getElementById("studio-video");
      if (nv && nv.getAttribute("src") === savedSrc) {
        nv.addEventListener("loadedmetadata", () => {
          try { nv.currentTime = savedTime; } catch { /* ignore */ }
        }, { once: true });
      }
    }
  }

  // ------------------------------------------------------------------ Global Delegated Events
  document.addEventListener("click", async e => {
    const winBtn = e.target.closest("[data-win]");
    if (winBtn && window.agentvidDesktop) {
      window.agentvidDesktop.windowAction(winBtn.dataset.win);
      return;
    }

    const navEl = e.target.closest("[data-nav]");
    if (navEl) {
      S.view = navEl.dataset.nav;
      if (S.view === "export") await refreshExportEstimate();
      render();
      return;
    }

    const actEl = e.target.closest("[data-act]");
    if (!actEl) return;
    const act = actEl.dataset.act;

    try {
      if (act === "preview-url") {
        const inp = document.getElementById("submit-url-input");
        S.ingestUrl = (inp ? inp.value : S.ingestUrl || "").trim();
        if (!S.ingestUrl) {
          toast("Paste a YouTube, Twitch, or Kick video URL first.", "error");
          return;
        }
        S.ingestPreviewLoading = true;
        S.ingestPreview = null;
        render();
        try {
          const res = await api("/api/v2/ingest/preview", { method: "POST", body: { url: S.ingestUrl } });
          S.ingestPreview = res.preview;
          toast(`Found: ${res.preview.title}`, "ok");
        } finally {
          S.ingestPreviewLoading = false;
          render();
        }
      }

      else if (act === "toggle-submit-captions") {
        S.ingestAutoCaptions = !S.ingestAutoCaptions;
        render();
      }

      else if (act === "start-url-ingest") {
        const inp = document.getElementById("submit-url-input");
        const psel = document.getElementById("submit-project-sel");
        const qsel = document.getElementById("submit-quality-sel");
        const rcsel = document.getElementById("submit-reel-count-sel");
        const rtsel = document.getElementById("submit-reel-timing-sel");
        const clsel = document.getElementById("submit-caption-lang-sel");
        const chk = document.getElementById("submit-immediate-chk");
        S.ingestUrl = (inp ? inp.value : S.ingestUrl || "").trim();
        S.ingestTargetProject = psel ? psel.value : "";
        S.ingestHeight = qsel ? Number(qsel.value) : 1080;
        S.ingestImmediate = chk ? chk.checked : true;
        if (rcsel) S.ingestReelCount = Number(rcsel.value) || 5;
        if (clsel) S.ingestCaptionLang = clsel.value || "auto";
        if (rtsel) {
          if (rtsel.value === "auto_ai") {
            S.ingestDurationMode = "auto_ai";
          } else {
            S.ingestDurationMode = "fixed";
            S.ingestTargetDuration = Number(rtsel.value) || 30;
          }
        }
        if (!S.ingestUrl) {
          toast("Paste a YouTube, Twitch, or Kick video URL first.", "error");
          return;
        }
        const res = await api("/api/v2/ingest/url", {
          method: "POST",
          body: {
            url: S.ingestUrl,
            project_id: S.ingestTargetProject || null,
            height: S.ingestHeight,
            process_immediately: S.ingestImmediate,
            reel_count: S.ingestReelCount,
            duration_mode: S.ingestDurationMode,
            target_duration: S.ingestTargetDuration,
            auto_captions: S.ingestAutoCaptions,
            caption_language: S.ingestCaptionLang,
          },
        });
        S.activeIngest = res.ingest;
        toast(`Fetching video for ${S.ingestReelCount} Peak Reels...`, "ok");
        render();
      }

      else if (act === "new-project") {
        showModal("Create New AgentVid Project", `
          <div class="field"><label>Project Name</label><input class="input" name="name" required placeholder="e.g. Launch Film Cut 01" autofocus /></div>
          <div class="field"><label>Description (optional)</label><textarea class="textarea" name="description" placeholder="Notes or target deliverables..."></textarea></div>
          <div class="row" style="justify-content:flex-end;margin-top:12px"><button type="submit" class="btn btn-primary">Create Project</button></div>
        `, async fd => {
          const res = await api("/api/v2/projects", {
            method: "POST",
            body: { name: fd.get("name"), description: fd.get("description") },
          });
          await refreshDashboardAndProjects();
          await openProject(res.project.id, true);
          toast(`Created '${res.project.name}'`, "ok");
        });
      }

      else if (act === "open-project") {
        await openProject(actEl.dataset.id, true);
      }

      else if (act === "rename-project") {
        const pid = actEl.dataset.id;
        const p = S.projectsList.find(x => x.id === pid);
        showModal("Rename Project", `
          <div class="field"><label>New Project Name</label><input class="input" name="name" required value="${esc(p ? p.name : "")}" autofocus /></div>
          <div class="row" style="justify-content:flex-end;margin-top:12px"><button type="submit" class="btn btn-primary">Save Name</button></div>
        `, async fd => {
          const res = await api(`/api/v2/projects/${pid}/rename`, { method: "PUT", body: { name: fd.get("name") } });
          if (S.project && S.project.id === pid) S.project = res.project;
          await refreshDashboardAndProjects();
          toast("Project renamed", "ok");
          render();
        });
      }

      else if (act === "duplicate-project") {
        const res = await api(`/api/v2/projects/${actEl.dataset.id}/duplicate`, { method: "POST", body: {} });
        await refreshDashboardAndProjects();
        toast(`Duplicated as '${res.project.name}'`, "ok");
        render();
      }

      else if (act === "delete-project") {
        const pid = actEl.dataset.id;
        if (!confirm("Delete this project and its local media/exports?")) return;
        await api(`/api/v2/projects/${pid}`, { method: "DELETE" });
        if (S.project && S.project.id === pid) S.project = null;
        await refreshDashboardAndProjects();
        toast("Project deleted", "ok");
        render();
      }

      else if (act === "quick-import") {
        await triggerMediaImport("video", true);
      }

      else if (act === "import-video") {
        await triggerMediaImport("video", false);
      }

      else if (act === "import-audio") {
        await triggerMediaImport("audio", false);
      }

      else if (act === "select-media" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/media/active`, {
          method: "PUT",
          body: { media_id: actEl.dataset.id },
        });
        S.project = res.project;
        render();
      }

      else if (act === "toggle-auto-mode") {
        const nextVal = !S.settings.auto_mode;
        const res = await api("/api/v2/settings", { method: "PUT", body: { auto_mode: nextVal } });
        S.settings = res.settings;
        toast(nextVal ? "AUTO Mode enabled (saved switches preserved)" : "MANUAL Mode enabled (saved switches preserved)", "ok");
        render();
      }

      else if (act === "toggle-auto-switch") {
        const key = actEl.dataset.key;
        const nextVal = !S.settings.automation[key];
        const res = await api("/api/v2/settings", { method: "PUT", body: { automation: { [key]: nextVal } } });
        S.settings = res.settings;
        render();
      }

      else if (act === "run-full-pipeline" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/automation/run`, {
          method: "POST",
          body: { trigger: "manual" },
        });
        S.automationStatus = res.automation;
        toast("Processing pipeline started", "ok");
        render();
      }

      else if (act === "run-manual-analyze" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/automation/run`, {
          method: "POST",
          body: { trigger: "manual", tasks: ["analyze", "face_detection", "virality_scoring"] },
        });
        S.automationStatus = res.automation;
        toast("Analyzing video shots, faces & virality...", "ok");
        render();
      }

      else if (act === "open-speech-modal") {
        const sr = await api("/api/v2/speech-model/status");
        S.speechModel = sr.speech_model;
        openSpeechModelModal(S.project && S.project.id);
      }

      else if (act === "extract-local-captions" && S.project) {
        const sr = await api("/api/v2/speech-model/status");
        S.speechModel = sr.speech_model;
        if (!S.speechModel.ready) {
          openSpeechModelModal(S.project.id);
          return;
        }
        const res = await api(`/api/v2/projects/${S.project.id}/automation/run`, {
          method: "POST",
          body: { trigger: "manual", tasks: ["caption_generation"] },
        });
        S.automationStatus = res.automation;
        toast("Extracting offline captions...", "ok");
        render();
      }

      else if (act === "run-manual-task" && S.project) {
        const task = actEl.dataset.task;
        const res = await api(`/api/v2/projects/${S.project.id}/automation/run`, {
          method: "POST",
          body: { trigger: "manual", tasks: [task] },
        });
        S.automationStatus = res.automation;
        toast(`Running ${task.replace(/_/g, " ")}...`, "ok");
        render();
      }

      else if (act === "run-face-detection" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/automation/run`, {
          method: "POST",
          body: { trigger: "manual", tasks: ["face_detection", "subject_tracking", "reframing"] },
        });
        S.automationStatus = res.automation;
        toast("Running local AI face detection & tracking...", "ok");
        render();
      }

      else if (act === "reset-face-tracking" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/faces/reset`, { method: "POST" });
        S.project = res.project;
        toast("Face tracking reset", "ok");
        render();
      }

      else if (act === "face-toggle" && S.project) {
        const field = actEl.dataset.field;
        const cur = (S.project.face_tracking && S.project.face_tracking.config) || S.settings.face_detection;
        const res = await api(`/api/v2/projects/${S.project.id}/faces/config`, {
          method: "PUT",
          body: { [field]: !cur[field] },
        });
        S.project = res.project;
        render();
      }

      else if (act === "set-primary-subject" && S.project) {
        const sid = Number(actEl.dataset.sid);
        const res = await api(`/api/v2/projects/${S.project.id}/faces/config`, {
          method: "PUT",
          body: { primary_subject_id: sid },
        });
        S.project = res.project;
        toast(`Focused primary tracking on Subject ${sid}`, "ok");
        render();
      }

      else if (act === "apply-global-reframe" && S.project) {
        const asp = actEl.dataset.aspect;
        pushUndoSnapshot();
        const rf = S.project.face_tracking && S.project.face_tracking.reframing_suggestions && S.project.face_tracking.reframing_suggestions[asp];
        await api(`/api/v2/projects/${S.project.id}/timeline`, { method: "PUT", body: { aspect: asp } });
        if (rf && S.selectedShotId) {
          await api(`/api/v2/projects/${S.project.id}/shots/${S.selectedShotId}`, {
            method: "PUT",
            body: { crop_mode: "face", pan_x: rf.pan_x, pan_y: rf.pan_y },
          });
        }
        await refreshProject();
        toast(`Applied smart ${asp} subject framing`, "ok");
        render();
      }

      else if (act === "auto-pause" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/automation/pause`, { method: "POST" });
        S.automationStatus = res.automation;
        render();
      }

      else if (act === "auto-resume" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/automation/resume`, { method: "POST" });
        S.automationStatus = res.automation;
        render();
      }

      else if (act === "auto-stop" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/automation/stop`, { method: "POST" });
        S.automationStatus = res.automation;
        render();
      }

      else if (act === "select-shot") {
        S.selectedShotId = actEl.dataset.id;
        render();
        const vid = document.getElementById("studio-video");
        const sh = (S.project.shots || []).find(s => s.id === S.selectedShotId);
        if (vid && sh) {
          vid.currentTime = Number(sh.trim_start || sh.start || 0);
          syncVideoOverlays();
        }
      }

      else if (act === "inspect-in-editor") {
        S.selectedShotId = actEl.dataset.id;
        S.view = "editor";
        S.editorRightTab = "shot";
        render();
      }

      else if (act === "toggle-shot-include" && S.project) {
        e.stopPropagation();
        const sh = (S.project.shots || []).find(s => s.id === actEl.dataset.id);
        if (!sh) return;
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/shots/${sh.id}`, {
          method: "PUT",
          body: { included: !(sh.edit && sh.edit.included !== false) },
        });
        S.project = res.project;
        render();
      }

      else if (act === "split-at-playhead" && S.project && S.selectedShotId) {
        const vid = document.getElementById("studio-video");
        const sh = (S.project.shots || []).find(s => s.id === S.selectedShotId);
        if (!sh) return;
        let splitAt = vid ? vid.currentTime : (sh.trim_start + sh.trim_end) / 2;
        if (splitAt <= sh.trim_start + 0.35 || splitAt >= sh.trim_end - 0.35) {
          splitAt = (sh.trim_start + sh.trim_end) / 2;
        }
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/shots/${sh.id}/split`, {
          method: "POST",
          body: { split_at: Number(splitAt.toFixed(2)) },
        });
        S.project = res.project;
        toast(`Split shot at ${fmtTime(splitAt)}`, "ok");
        render();
      }

      else if (act === "merge-next-shot" && S.project && S.selectedShotId) {
        const shots = S.project.shots || [];
        const idx = shots.findIndex(s => s.id === S.selectedShotId);
        if (idx < 0 || idx >= shots.length - 1) {
          toast("Select a shot with a following shot to merge.", "error");
          return;
        }
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/shots/merge`, {
          method: "POST",
          body: { shot_a: shots[idx].id, shot_b: shots[idx + 1].id },
        });
        S.project = res.project;
        toast("Merged adjacent shots", "ok");
        render();
      }

      else if ((act === "move-shot-left" || act === "move-shot-right") && S.project && S.selectedShotId) {
        const shots = [...(S.project.shots || [])];
        const idx = shots.findIndex(s => s.id === S.selectedShotId);
        const swap = act === "move-shot-left" ? idx - 1 : idx + 1;
        if (idx < 0 || swap < 0 || swap >= shots.length) return;
        pushUndoSnapshot();
        [shots[idx], shots[swap]] = [shots[swap], shots[idx]];
        const res = await api(`/api/v2/projects/${S.project.id}/shots/reorder`, {
          method: "PUT",
          body: { ordered_ids: shots.map(s => s.id) },
        });
        S.project = res.project;
        render();
      }

      else if (act === "apply-suggestion" && S.project) {
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/shots/${actEl.dataset.id}/apply-suggestion`, {
          method: "POST",
          body: { action: actEl.dataset.sug },
        });
        S.project = res.project;
        toast("Applied AI suggestion", "ok");
        render();
      }

      else if (act === "apply-recommended-seq" && S.project) {
        const seq = (S.project.virality && S.project.virality.recommended_sequence) || [];
        if (!seq.length) return;
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/shots/reorder`, {
          method: "PUT",
          body: { ordered_ids: seq },
        });
        S.project = res.project;
        toast("Applied recommended high-virality sequence to timeline", "ok");
        S.view = "editor";
        render();
      }

      else if (act === "editor-tab") {
        S.editorRightTab = actEl.dataset.tab;
        render();
      }

      else if (act === "toggle-editor-captions" && S.project) {
        const cur = (S.project.timeline && S.project.timeline.caption_config) || {};
        const nextOn = cur.enabled === false;
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { caption_config: { enabled: nextOn } },
        });
        S.project = res.project;
        toast(nextOn ? "Auto-Captions turned ON" : "Auto-Captions turned OFF", "ok");
        render();
        syncVideoOverlays();
      }

      else if (act === "generate-captions-now" && S.project) {
        if (S.captionGenBusy) return;
        const lang = ((S.project.timeline && S.project.timeline.caption_config && S.project.timeline.caption_config.language) || "auto");
        if (!S.aiAudioReady && !(S.speechModel && S.speechModel.ready)) {
          if (lang !== "auto" && lang !== "en") {
            toast("Add a Gemini, Groq, or OpenAI API key in Settings for non-English AI voice captions.", "error");
            S.view = "settings";
            render();
            return;
          }
          openSpeechModelModal(S.project.id);
          return;
        }
        S.captionGenBusy = true;
        render();
        toast("Generating voice-synchronized captions across your Reels...");
        try {
          const res = await api(`/api/v2/projects/${S.project.id}/captions/generate`, {
            method: "POST",
            body: { language: lang, only_shots: true },
          });
          S.project = res.project;
          toast(res.note || `Generated ${res.cues_count} voice-synced captions`, res.cues_count > 0 ? "ok" : "");
        } finally {
          S.captionGenBusy = false;
          render();
          syncVideoOverlays();
        }
      }

      else if (act === "set-cap-x-snap" && S.project) {
        const xv = Number(actEl.dataset.x || 50);
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { caption_config: { x_offset: xv } },
        });
        S.project = res.project;
        render();
        syncVideoOverlays();
      }

      else if (act === "set-cap-pos-snap" && S.project) {
        const yv = Number(actEl.dataset.y || 82);
        const pos = actEl.dataset.pos || "bottom";
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { caption_config: { y_offset: yv, position: pos } },
        });
        S.project = res.project;
        render();
        syncVideoOverlays();
      }

      else if (act === "export-all-timeline-reels" && S.project) {
        const activeCount = (S.project.shots || []).filter(s => (s.edit || {}).included !== false).length;
        if (!activeCount) {
          toast("No active Reels to export.", "error");
          return;
        }
        const res = await api(`/api/v2/projects/${S.project.id}/export/reels`, {
          method: "POST",
          body: {
            use_timeline_reels: true,
            count: activeCount,
            aspect: (S.project.timeline && S.project.timeline.aspect) || "9:16",
            resolution: S.exportOpts.resolution || "1080p",
            codec: S.exportOpts.codec || "h264",
            fps: S.exportOpts.fps || 30,
            quality: S.exportOpts.quality || "standard",
            audio_bitrate: S.exportOpts.audio_bitrate || "192k",
            output_dir: S.exportOpts.output_dir || "",
          },
        });
        S.activeExport = res.export;
        S.view = "export";
        toast(`Exporting all ${activeCount} Peak Reels...`, "ok");
        render();
      }

      else if (act === "toggle-face-overlay") {
        S.showFaceOverlay = !S.showFaceOverlay;
        render();
        syncVideoOverlays();
      }

      else if (act === "toggle-reframe-guide") {
        S.showReframeGuide = !S.showReframeGuide;
        render();
        syncVideoOverlays();
      }

      else if (act === "toggle-play") {
        const vid = document.getElementById("studio-video");
        if (!vid) return;
        S.playingShotEnd = null;
        if (vid.paused) vid.play();
        else vid.pause();
      }

      else if (act === "play-selected-shot" && S.project && S.selectedShotId) {
        const vid = document.getElementById("studio-video");
        const sh = (S.project.shots || []).find(s => s.id === S.selectedShotId);
        if (!vid || !sh) return;
        vid.currentTime = Number(sh.trim_start || sh.start || 0);
        S.playingShotEnd = Number(sh.trim_end || sh.end);
        vid.play();
      }

      else if (act === "save-project" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/save`, {
          method: "POST",
          body: { timeline: S.project.timeline, shots: S.project.shots },
        });
        S.project = res.project;
        dirty = false;
        toast("Project saved locally", "ok");
        render();
      }

      else if (act === "recover-accept" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/recover`, { method: "POST", body: { accept: true } });
        S.project = res.project;
        toast("Autosaved session recovered", "ok");
        render();
      }

      else if (act === "recover-discard" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/recover`, { method: "POST", body: { accept: false } });
        S.project = res.project;
        render();
      }

      else if (act === "undo") { await doUndo(); }
      else if (act === "redo") { await doRedo(); }

      else if (act === "upload-font") {
        const finp = document.getElementById("hidden-font-input");
        finp.value = "";
        finp.onchange = async () => {
          const f = finp.files && finp.files[0];
          if (!f) return;
          const fd = new FormData();
          fd.append("file", f);
          toast(`Installing font '${f.name}'...`);
          try {
            const res = await api("/api/v2/fonts/upload", { method: "POST", body: fd });
            S.fonts = res.fonts || [];
            injectFontFaces(S.fonts);
            if (S.project && res.font && res.font.family) {
              const tlRes = await api(`/api/v2/projects/${S.project.id}/timeline`, {
                method: "PUT",
                body: { caption_config: { font: res.font.family } },
              });
              S.project = tlRes.project;
            }
            toast(`Custom font '${res.font.family}' installed & applied`, "ok");
            render();
          } catch (err) {
            toast(err.message, "error");
          }
        };
        finp.click();
      }

      else if (act === "delete-font") {
        const fname = actEl.dataset.file;
        const res = await api(`/api/v2/fonts/${encodeURIComponent(fname)}`, { method: "DELETE" });
        S.fonts = res.fonts || [];
        injectFontFaces(S.fonts);
        toast("Custom font removed", "ok");
        render();
      }

      else if (act === "set-cap-style" && S.project) {
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { caption_config: { style: actEl.dataset.val } },
        });
        S.project = res.project;
        render();
      }

      else if (act === "set-cap-anim" && S.project) {
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { caption_config: { animation: actEl.dataset.val } },
        });
        S.project = res.project;
        render();
      }

      else if (act === "cap-toggle" && S.project) {
        const f = actEl.dataset.field;
        const cur = (S.project.timeline && S.project.timeline.caption_config) || {};
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { caption_config: { [f]: !cur[f] } },
        });
        S.project = res.project;
        render();
      }

      else if (act === "add-caption-cue" && S.project) {
        pushUndoSnapshot();
        const cues = [...((S.project.timeline && S.project.timeline.captions) || [])];
        const lastEnd = cues.length ? Number(cues[cues.length - 1].end || 0) : 0;
        cues.push({
          id: "cap_" + Math.random().toString(16).slice(2, 8),
          start: Number(lastEnd.toFixed(1)),
          end: Number((lastEnd + 2.5).toFixed(1)),
          text: "Your kinetic studio caption here",
          words: [],
        });
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { captions: cues },
        });
        S.project = res.project;
        render();
      }

      else if (act === "del-caption-cue" && S.project) {
        pushUndoSnapshot();
        const idx = Number(actEl.dataset.idx);
        const cues = ((S.project.timeline && S.project.timeline.captions) || []).filter((_, i) => i !== idx);
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { captions: cues },
        });
        S.project = res.project;
        render();
      }

      else if (act === "export-single-shot" && S.project) {
        S.exportOpts.mode = "shot";
        S.exportOpts.shot_id = actEl.dataset.id;
        S.view = "export";
        await refreshExportEstimate();
        render();
      }

      else if (act === "start-reels-pack" && S.project) {
        const cnt = Number(document.getElementById("reels-count-sel")?.value || 5);
        const rawDur = document.getElementById("reels-dur-sel")?.value || "timeline";
        const useTimeline = rawDur === "timeline";
        const dur = useTimeline ? 30 : Number(rawDur || 30);
        const res = await api(`/api/v2/projects/${S.project.id}/export/reels`, {
          method: "POST",
          body: {
            use_timeline_reels: useTimeline,
            count: cnt,
            target_duration: dur,
            aspect: S.exportOpts.aspect || (S.project.timeline && S.project.timeline.aspect) || "9:16",
            resolution: S.exportOpts.resolution || "1080p",
            codec: S.exportOpts.codec || "h264",
            fps: S.exportOpts.fps || 30,
            quality: S.exportOpts.quality || "standard",
            audio_bitrate: S.exportOpts.audio_bitrate || "192k",
            output_dir: S.exportOpts.output_dir || "",
          },
        });
        S.activeExport = res.export;
        toast(useTimeline ? `Exporting ${cnt} Peak Reels from timeline...` : `Generating ${cnt} x ${dur}s Viral Reels...`, "ok");
        render();
      }

      else if (act === "start-export" && S.project) {
        const res = await api(`/api/v2/projects/${S.project.id}/export`, {
          method: "POST",
          body: S.exportOpts,
        });
        S.activeExport = res.export;
        toast("FFmpeg export started", "ok");
        render();
      }

      else if (act === "cancel-export" && S.activeExport) {
        const res = await api(`/api/v2/exports/${S.activeExport.id}/cancel`, { method: "POST" });
        S.activeExport = res.export;
        render();
      }

      else if (act === "pick-export-dir" && window.agentvidDesktop) {
        const dir = await window.agentvidDesktop.pickDirectory();
        if (dir) {
          S.exportOpts.output_dir = dir;
          await api("/api/v2/settings", { method: "PUT", body: { export_defaults: { output_dir: dir } } });
          render();
        }
      }

      else if (act === "reveal-path" && window.agentvidDesktop) {
        window.agentvidDesktop.revealPath(actEl.dataset.path);
      }

      else if (act === "open-path" && window.agentvidDesktop) {
        window.agentvidDesktop.openPath(actEl.dataset.path);
      }

      else if (act === "open-external") {
        const url = actEl.dataset.url;
        if (window.agentvidDesktop && window.agentvidDesktop.openExternal) {
          window.agentvidDesktop.openExternal(url);
        } else {
          window.open(url, "_blank", "noopener,noreferrer");
        }
      }

      else if (act === "ai-quick" && S.project) {
        const q = actEl.dataset.q;
        S.assistantMessages.push({ role: "user", text: actEl.textContent.trim() });
        render();
        const res = await api(`/api/v2/projects/${S.project.id}/assistant`, {
          method: "POST",
          body: { action: q, prompt: actEl.textContent.trim() },
        });
        S.assistantMessages.push({ role: "ai", text: res.reply, meta: `Source: ${res.mode}` });
        render();
      }

      else if (act === "ai-send" && S.project) {
        const inp = document.getElementById("ai-chat-input");
        const txt = (inp && inp.value || "").trim();
        if (!txt) return;
        S.assistantMessages.push({ role: "user", text: txt });
        render();
        const res = await api(`/api/v2/projects/${S.project.id}/assistant`, {
          method: "POST",
          body: { action: "chat", prompt: txt },
        });
        S.assistantMessages.push({ role: "ai", text: res.reply, meta: `Source: ${res.mode}` });
        render();
      }

      else if (act === "save-ai") {
        const provider = document.getElementById("ai-provider-sel").value;
        const models = document.getElementById("ai-models-inp").value.split(",").map(s => s.trim()).filter(Boolean);
        const base_url = document.getElementById("ai-url-inp").value.trim();
        const rawKey = document.getElementById("ai-key-inp").value;
        const res = await api("/api/v2/settings/ai", {
          method: "PUT",
          body: { provider, models, base_url, key: rawKey === "" ? null : rawKey },
        });
        S.aiConfig = res.ai;
        S.aiAudioReady = !!(res.ai && res.ai.ready && ["gemini", "openai", "groq"].includes(res.ai.provider));
        toast("AI provider settings saved locally", "ok");
        render();
      }

      else if (act === "test-ai") {
        toast("Testing AI provider connection...");
        const res = await api("/api/v2/settings/ai/test", { method: "POST" });
        toast(`Connected to ${res.model} (${res.tokens} tokens)`, "ok");
      }

      else if (act === "set-reel-count-chip") {
        const val = Number(actEl.dataset.val || 5);
        const res = await api("/api/v2/settings", { method: "PUT", body: { reels: { count: val } } });
        S.settings = res.settings;
        S.ingestReelCount = val;
        toast(`Default set to ${val} Peak Reels per video`, "ok");
        render();
      }

      else if (act === "toggle-reel-autocaptions") {
        const cur = (S.settings.reels || {}).auto_captions !== false;
        const res = await api("/api/v2/settings", { method: "PUT", body: { reels: { auto_captions: !cur } } });
        S.settings = res.settings;
        S.ingestAutoCaptions = !cur;
        render();
      }

      else if (act === "set-cap-def-chip") {
        const field = actEl.dataset.field;
        const val = Number(actEl.dataset.val || 50);
        const res = await api("/api/v2/settings", { method: "PUT", body: { caption_defaults: { [field]: val } } });
        S.settings = res.settings;
        render();
      }

      else if (act === "apply-cap-defaults-project" && S.project) {
        const cd = (S.settings && S.settings.caption_defaults) || {};
        pushUndoSnapshot();
        const pos = (cd.y_offset ?? 80) < 33 ? "top" : (cd.y_offset ?? 80) > 66 ? "bottom" : "center";
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: {
            caption_config: {
              language: cd.language || "auto",
              x_offset: Number(cd.x_offset ?? 50),
              y_offset: Number(cd.y_offset ?? 80),
              font_size: Number(cd.font_size || 64),
              position: pos,
            },
          },
        });
        S.project = res.project;
        toast("Applied caption language, placement (X/Y) & size to open project", "ok");
        render();
      }

      else if (act === "privacy-toggle") {
        const field = actEl.dataset.field;
        const cur = S.settings.privacy || {};
        const res = await api("/api/v2/settings", { method: "PUT", body: { privacy: { [field]: !cur[field] } } });
        S.settings = res.settings;
        render();
      }
    } catch (err) {
      toast(err.message || "Action failed", "error");
    }
  });

  // Delegated change / input handlers
  document.addEventListener("change", async e => {
    const t = e.target;
    try {
      if (t.dataset.bind) {
        S[t.dataset.bind] = t.value;
        render();
        return;
      }
      if (t.dataset.act === "set-timeline-aspect" && S.project) {
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, { method: "PUT", body: { aspect: t.value } });
        S.project = res.project;
        S.exportOpts.aspect = t.value;
        render();
        syncVideoOverlays();
      }
      else if (t.dataset.act === "set-bg-music" && S.project) {
        pushUndoSnapshot();
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, { method: "PUT", body: { background_music: t.value || null } });
        S.project = res.project;
        render();
      }
      else if (t.dataset.shotEdit && S.project) {
        pushUndoSnapshot();
        const field = t.dataset.shotEdit;
        const val = ["transition", "text_overlay"].includes(field) ? t.value : Number(t.value);
        const res = await api(`/api/v2/projects/${S.project.id}/shots/${t.dataset.id}`, {
          method: "PUT",
          body: { [field]: val },
        });
        S.project = res.project;
        render();
        syncVideoOverlays();
      }
      else if (t.dataset.faceCfg && S.project) {
        const field = t.dataset.faceCfg;
        const val = field === "mode" ? t.value : Number(t.value);
        const res = await api(`/api/v2/projects/${S.project.id}/faces/config`, {
          method: "PUT",
          body: { [field]: val },
        });
        S.project = res.project;
        render();
      }
      else if (t.id === "submit-reel-count-sel") {
        S.ingestReelCount = Number(t.value) || 5;
        render();
      }
      else if (t.id === "submit-reel-timing-sel") {
        if (t.value === "auto_ai") {
          S.ingestDurationMode = "auto_ai";
        } else {
          S.ingestDurationMode = "fixed";
          S.ingestTargetDuration = Number(t.value) || 30;
        }
        render();
      }
      else if (t.id === "submit-caption-lang-sel") {
        S.ingestCaptionLang = t.value || "auto";
        render();
      }
      else if (t.dataset.capDef) {
        const k = t.dataset.capDef;
        const val = ["language", "position"].includes(k) ? t.value : Number(t.value);
        const res = await api("/api/v2/settings", { method: "PUT", body: { caption_defaults: { [k]: val } } });
        S.settings = res.settings;
        if (k === "language") S.ingestCaptionLang = val;
        render();
      }
      else if (t.dataset.reelCfg) {
        const k = t.dataset.reelCfg;
        const val = ["duration_mode", "aspect"].includes(k) ? t.value : Number(t.value);
        const res = await api("/api/v2/settings", { method: "PUT", body: { reels: { [k]: val } } });
        S.settings = res.settings;
        if (k === "count") S.ingestReelCount = val;
        if (k === "duration_mode") S.ingestDurationMode = val;
        if (k === "target_duration") S.ingestTargetDuration = val;
        render();
      }
      else if (t.dataset.capCfg && S.project) {
        pushUndoSnapshot();
        const field = t.dataset.capCfg;
        const val = ["language", "font", "position", "color", "highlight_color", "background"].includes(field) ? t.value : Number(t.value);
        const res = await api(`/api/v2/projects/${S.project.id}/timeline`, {
          method: "PUT",
          body: { caption_config: { [field]: val } },
        });
        S.project = res.project;
        render();
        syncVideoOverlays();
      }
      else if (t.dataset.cueIdx !== undefined && S.project) {
        pushUndoSnapshot();
        const idx = Number(t.dataset.cueIdx);
        const field = t.dataset.cueField;
        const cues = JSON.parse(JSON.stringify((S.project.timeline && S.project.timeline.captions) || []));
        if (cues[idx]) {
          cues[idx][field] = field === "text" ? t.value : Number(t.value);
          const res = await api(`/api/v2/projects/${S.project.id}/timeline`, { method: "PUT", body: { captions: cues } });
          S.project = res.project;
          render();
        }
      }
      else if (t.dataset.expOpt) {
        const k = t.dataset.expOpt;
        S.exportOpts[k] = k === "fps" ? Number(t.value) : t.value;
        await refreshExportEstimate();
        render();
      }
      else if (t.dataset.perfCfg) {
        const k = t.dataset.perfCfg;
        const val = k === "hw_accel" ? t.value : Number(t.value);
        const res = await api("/api/v2/settings", { method: "PUT", body: { performance: { [k]: val } } });
        S.settings = res.settings;
        render();
      }
    } catch (err) {
      toast(err.message || "Update failed", "error");
    }
  });

  document.addEventListener("input", e => {
    if (e.target && e.target.id === "submit-url-input") {
      S.ingestUrl = e.target.value;
    }
    if (e.target && e.target.id === "editor-cap-x-slider") {
      const xv = Number(e.target.value || 50);
      const lbl = document.getElementById("editor-cap-x-label");
      if (lbl) lbl.textContent = `${xv}%`;
      const capEl = document.getElementById("live-caption-overlay");
      const vid = document.getElementById("studio-video");
      if (capEl) {
        const shots = (S.project && S.project.shots) || [];
        const cr = computeLiveCropRect(vid, shots.find(s => s.id === S.selectedShotId) || shots[0] || null);
        capEl.style.left = `${((cr.x + cr.w * (xv / 100)) * 100).toFixed(2)}%`;
      }
    }
    if (e.target && e.target.id === "editor-cap-y-slider") {
      const yv = Number(e.target.value || 80);
      const lbl = document.getElementById("editor-cap-y-label");
      if (lbl) lbl.textContent = `${yv}%`;
      const capEl = document.getElementById("live-caption-overlay");
      const vid = document.getElementById("studio-video");
      if (capEl) {
        const shots = (S.project && S.project.shots) || [];
        const cr = computeLiveCropRect(vid, shots.find(s => s.id === S.selectedShotId) || shots[0] || null);
        capEl.style.top = `${((cr.y + cr.h * (yv / 100)) * 100).toFixed(2)}%`;
      }
    }
    if (e.target && e.target.id === "editor-cap-size-slider") {
      const sv = Number(e.target.value || 64);
      const lbl = document.getElementById("editor-cap-size-label");
      if (lbl) lbl.textContent = `${sv}px`;
      const capEl = document.getElementById("live-caption-overlay");
      if (capEl) capEl.style.fontSize = `${Math.max(12, Math.round(sv * 0.34))}px`;
    }
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Enter" && e.target && e.target.id === "submit-url-input") {
      e.preventDefault();
      document.querySelector('[data-act="start-url-ingest"]')?.click();
    }
    if (e.key === "Enter" && e.target && e.target.id === "ai-chat-input") {
      document.querySelector('[data-act="ai-send"]')?.click();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s" && S.project) {
      e.preventDefault();
      document.querySelector('[data-act="save-project"]')?.click();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey && S.undoStack.length) {
      if (document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
        e.preventDefault();
        doUndo();
      }
    }
  });

  // Boot AgentVid Studio
  loadBootstrap().then(startBackgroundTimers).catch(err => {
    toast(`Failed to connect to AgentVid Studio Engine: ${err.message}`, "error");
  });
})();
