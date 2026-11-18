/* AgentVid Studio — All 9 Navigation View Renderers */
window.AVViews = (() => {
  const { svg, esc, fmtTime, fmtDate, scoreClass } = window.AVIcons;

  const AUTOMATION_META = [
    ["scene_detection", "Automatic Scene Detection", "Detect visual scene cuts using frame histogram & luminance analysis"],
    ["shot_segmentation", "Automatic Shot Segmentation", "Split source footage into individual shots with thumbnails"],
    ["face_detection", "Automatic Face Detection", "Run local OpenCV multi-pass face & eye visibility detection"],
    ["subject_tracking", "Automatic Subject Tracking", "Track primary and secondary subjects across consecutive frames"],
    ["silence_detection", "Automatic Silence Detection", "Detect dead air, pauses, and vocal speech activity windows"],
    ["caption_generation", "Automatic Caption Generation", "Extract word-timed captions when local speech model is available"],
    ["highlight_detection", "Automatic Highlight Detection", "Surface high-energy peaks and top standalone clip candidates"],
    ["virality_scoring", "Automatic Virality Scoring", "Compute 15-dimension weighted virality scores for every shot"],
    ["reframing", "Automatic Reframing", "Compute smart 9:16, 1:1, and 16:9 crop framing around subjects"],
    ["zoom_suggestions", "Automatic Zoom Suggestions", "Recommend punch-in framing on subjects and static takes"],
    ["transition_suggestions", "Automatic Transition Suggestions", "Recommend fade/dissolve transitions matched to scene mood"],
    ["broll_suggestions", "Automatic B-Roll Suggestions", "Identify steady dialogue moments ideal for visual cutaways"],
    ["editing_recommendations", "Automatic Editing Recommendations", "Build an approval-based editing plan with trim & pacing tips"],
    ["export_preparation", "Automatic Export Preparation", "Pre-calculate export profiles after analysis completes"],
  ];

  function renderSubmitVideo(S) {
    const ing = S.activeIngest;
    const prev = S.ingestPreview;
    const busy = ing && (ing.status === "starting" || ing.status === "downloading" || ing.status === "importing");
    const projs = S.projectsList || [];
    const reelsCfg = (S.settings && S.settings.reels) || {};
    const capDef = (S.settings && S.settings.caption_defaults) || {};
    const langs = (S.captionLanguages && S.captionLanguages.length) ? S.captionLanguages : [
      { id: "auto", label: "Auto-Detect Spoken Language" },
      { id: "en", label: "English" },
      { id: "hi-Latn", label: "Hinglish (Hindi in English letters)" },
      { id: "hi", label: "Hindi (हिन्दी)" },
    ];
    const reelCount = Number(S.ingestReelCount || reelsCfg.count || 5);
    const durMode = S.ingestDurationMode || reelsCfg.duration_mode || "auto_ai";
    const targetDur = Number(S.ingestTargetDuration || reelsCfg.target_duration || 30);
    const autoCaps = S.ingestAutoCaptions !== undefined ? !!S.ingestAutoCaptions : (reelsCfg.auto_captions !== false);
    const capLang = S.ingestCaptionLang || capDef.language || "auto";
    const timingVal = durMode === "auto_ai" ? "auto_ai" : String(targetDur);
    const aiReady = !!(S.aiConfig && S.aiConfig.ready);
    const countOpts = Array.from(new Set([3, 5, 8, 10, 12, 15, 20, reelCount])).sort((a, b) => a - b);

    return `
      <div class="scroll-view">
        <div class="submit-hero-wrap">
          <div class="submit-eyebrow"><span class="submit-eyebrow-dot"></span> AI Peak Reel Finder · Podcasts, YouTube, Twitch &amp; Local</div>
          <h1 class="submit-title">Submit a podcast or video link</h1>
          <p class="submit-subtitle">
            Paste any long-form video or 1-hour podcast URL. Pick how many Reels you want and their duration —
            AgentVid analyzes peak moments across the full episode, tracks faces in 9:16, and prepares ready-to-post Reels.
          </p>

          <div class="submit-card">
            <div class="field" style="margin-bottom:14px">
              <label style="font-size:12px;color:var(--text-1);margin-bottom:4px">Video or Podcast URL</label>
              <div class="submit-url-box">
                <span class="muted" style="display:grid;place-items:center">${svg("link", 16)}</span>
                <input id="submit-url-input" type="url" placeholder="Paste a YouTube, Twitch, or Kick link..." value="${esc(S.ingestUrl || "")}" ${busy ? "disabled" : ""} />
                <button class="btn btn-sm" data-act="preview-url" ${busy ? "disabled" : ""}>${S.ingestPreviewLoading ? "Checking..." : "Preview"}</button>
              </div>
            </div>

            ${prev ? `
              <div class="switch-row" style="margin-bottom:14px;padding:10px 12px;border-color:rgba(0,102,255,0.45);background:rgba(0,102,255,0.08)">
                <div class="row" style="min-width:0;gap:12px">
                  ${prev.thumb ? `<img src="${esc(prev.thumb)}" style="width:92px;height:54px;border-radius:8px;object-fit:cover;flex-shrink:0" />` : `<div style="width:92px;height:54px;border-radius:8px;background:#0a0c12;display:grid;place-items:center">${svg("film", 20)}</div>`}
                  <div style="min-width:0">
                    <div class="switch-row-title" style="font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(prev.title)}</div>
                    <div class="switch-row-desc">${esc(prev.uploader || "Source Channel")} · Duration ${fmtTime(prev.duration)} ${prev.is_live ? "· LIVE" : ""}</div>
                  </div>
                </div>
                <span class="badge score-high">Verified</span>
              </div>
            ` : ""}

            <div class="submit-reels-strip">
              <div class="field" style="margin:0">
                <label>Reels to Generate</label>
                <select class="select" id="submit-reel-count-sel" ${busy ? "disabled" : ""}>
                  ${countOpts.map(n => `<option value="${n}" ${reelCount === n ? "selected" : ""}>${n} Peak Reels</option>`).join("")}
                </select>
              </div>
              <div class="field" style="margin:0">
                <label>Reel Duration (Shorts / Reels)</label>
                <select class="select" id="submit-reel-timing-sel" ${busy ? "disabled" : ""}>
                  <option value="auto_ai" ${timingVal === "auto_ai" ? "selected" : ""}>AI Decides Best Length (18–58s)</option>
                  <option value="15" ${timingVal === "15" ? "selected" : ""}>Fixed · 15 seconds</option>
                  <option value="30" ${timingVal === "30" ? "selected" : ""}>Fixed · 30 seconds</option>
                  <option value="45" ${timingVal === "45" ? "selected" : ""}>Fixed · 45 seconds</option>
                  <option value="60" ${timingVal === "60" ? "selected" : ""}>Fixed · 60 seconds</option>
                </select>
              </div>
              <div class="field" style="margin:0">
                <label>Auto-Captions</label>
                <button type="button" class="cap-toggle-pill ${autoCaps ? "is-on" : ""}" style="height:36px;padding:0 12px;border-radius:var(--radius-sm)" data-act="toggle-submit-captions" ${busy ? "disabled" : ""}>
                  <span class="cap-dot"></span>
                  <span>${autoCaps ? "ON" : "OFF"}</span>
                </button>
              </div>
            </div>

            <div class="grid-2" style="gap:10px;margin-bottom:14px">
              <div class="field" style="margin:0">
                <label>Caption Language</label>
                <select class="select" id="submit-caption-lang-sel" ${busy ? "disabled" : ""}>
                  ${langs.map(l => `<option value="${esc(l.id)}" ${capLang === l.id ? "selected" : ""}>${esc(l.label)}</option>`).join("")}
                </select>
              </div>
              <div class="field" style="margin:0">
                <label>Download Quality</label>
                <select class="select" id="submit-quality-sel" ${busy ? "disabled" : ""}>
                  <option value="1080" ${Number(S.ingestHeight || 1080) === 1080 ? "selected" : ""}>1080p Full HD (Recommended)</option>
                  <option value="720" ${Number(S.ingestHeight) === 720 ? "selected" : ""}>720p HD (Faster Download)</option>
                  <option value="2160" ${Number(S.ingestHeight) === 2160 ? "selected" : ""}>Up to 4K Ultra HD</option>
                </select>
              </div>
            </div>

            <div class="field" style="margin-bottom:14px">
              <label>Destination Project</label>
              <select class="select" id="submit-project-sel" ${busy ? "disabled" : ""}>
                <option value="">Create New Project Automatically</option>
                ${projs.map(p => `<option value="${esc(p.id)}" ${S.ingestTargetProject === p.id ? "selected" : ""}>Add to: ${esc(p.name)}</option>`).join("")}
              </select>
            </div>

            <div class="row-between wrap" style="gap:10px;margin-bottom:12px;padding:8px 11px;border-radius:8px;background:rgba(255,255,255,0.02);border:1px solid var(--border)">
              <div class="row" style="gap:8px;font-size:11.5px">
                <span class="badge ${aiReady ? "score-high" : "score-mod"}">${aiReady ? `AI API: ${esc(S.aiConfig.provider || "Ready")}` : "Local Peak Fallback"}</span>
                <span class="muted">${aiReady ? "AI scans full transcript to pick the exact peak moments across the episode." : "Add an AI API key in Settings so AI picks the best talking moments across 1-hr podcasts."}</span>
              </div>
              ${!aiReady ? `<button class="btn btn-sm" data-nav="settings">${svg("settings", 12)} Set AI Key</button>` : ""}
            </div>

            <div class="row-between wrap" style="gap:12px;padding-top:4px">
              <label class="row" style="cursor:pointer;font-size:12.5px;color:var(--text-1)">
                <input type="checkbox" id="submit-immediate-chk" ${S.ingestImmediate !== false ? "checked" : ""} style="accent-color:var(--accent);width:15px;height:15px" ${busy ? "disabled" : ""} />
                ${svg("zap", 14)}
                <span>Extract ${reelCount} Peak Reels &amp; track faces automatically</span>
              </label>

              <button class="btn-white-cta" data-act="start-url-ingest" ${busy ? "disabled" : ""}>
                ${busy ? `${svg("loader", 14, "spin")} Fetching Video...` : `Fetch &amp; Start Editing ${svg("arrowRight", 15)}`}
              </button>
            </div>

            ${ing ? `
              <div style="margin-top:16px;padding-top:14px;border-top:1px solid var(--border)">
                <div class="row-between" style="margin-bottom:6px;font-size:12px">
                  <span style="color:${ing.status === "error" ? "var(--rose)" : "var(--accent-bright)"}"><strong>${esc(ing.status).toUpperCase()}</strong> — ${esc(ing.error || ing.stage)}</span>
                  <span class="mono">${Math.round((ing.progress || 0) * 100)}%</span>
                </div>
                <div class="progress-bar"><div class="progress-fill" style="width:${Math.round((ing.progress || 0) * 100)}%"></div></div>
                ${ing.status === "done" && ing.project_id ? `
                  <div class="row" style="margin-top:10px;justify-content:flex-end">
                    <button class="btn btn-primary btn-sm" data-act="open-project" data-id="${esc(ing.project_id)}">Open in Studio Editor</button>
                  </div>
                ` : ""}
              </div>
            ` : ""}
          </div>

          <div class="row wrap" style="margin-top:18px;gap:10px;color:var(--text-2);font-size:12px">
            <span>Have footage on this PC already?</span>
            <button class="btn btn-sm" data-act="quick-import">${svg("upload", 13)} Import Local Video File</button>
            <button class="btn btn-sm" data-nav="projects">${svg("folder", 13)} Open Existing Project</button>
            <button class="btn btn-sm" data-nav="settings">${svg("settings", 13)} Reel Defaults &amp; AI Key</button>
          </div>
        </div>
      </div>
    `;
  }

  function renderHome(S) {
    const dash = S.dashboard || {};
    const autoOn = !!(S.settings && S.settings.auto_mode);
    const projs = dash.recent_projects || [];
    const activity = dash.recent_activity || [];
    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">AgentVid Studio</h1>
            <p class="page-sub">AI Video Creation &amp; Editing Studio · Creative Creature (WE.ARECC)</p>
          </div>
          <div class="row">
            <button class="btn" data-nav="submit">${svg("link", 14)} Submit Video Link</button>
            <button class="btn" data-act="new-project">${svg("plus", 14)} New Project</button>
            <button class="btn btn-primary" data-act="quick-import">${svg("upload", 14)} Import Local Video</button>
          </div>
        </div>

        <div class="grid-4" style="margin-bottom:16px">
          <div class="stat-card">
            <div class="stat-label">Projects</div>
            <div class="stat-value">${dash.project_count || 0}</div>
            <div class="stat-sub">Stored locally on disk</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Analyzed Shots</div>
            <div class="stat-value">${dash.total_analyzed_shots || 0}</div>
            <div class="stat-sub">Scene-segmented shots</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">High-Potential Shots</div>
            <div class="stat-value" style="color:var(--emerald)">${dash.high_potential_shots || 0}</div>
            <div class="stat-sub">Virality score 75+</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Automation Engine</div>
            <div class="stat-value" style="color:${autoOn ? "var(--cyan)" : "var(--text-1)"}">${autoOn ? "AUTO" : "MANUAL"}</div>
            <div class="stat-sub">${autoOn ? "Auto-analyzing imports via active switches" : "Full manual trigger control"}</div>
          </div>
        </div>

        <div class="grid-2">
          <div class="panel">
            <div class="panel-header">
              <h2 class="panel-title">${svg("folder", 15)} Recent Projects</h2>
              <button class="btn btn-sm" data-nav="projects">View All</button>
            </div>
            ${projs.length === 0 ? `
              <div class="empty-state">
                ${svg("film", 28)}
                <div>No projects yet. Create a project or import a video to start editing.</div>
                <button class="btn btn-primary btn-sm" data-act="quick-import">${svg("upload", 13)} Import Your First Video</button>
              </div>
            ` : `
              <div style="display:flex;flex-direction:column;gap:8px">
                ${projs.slice(0, 6).map(p => `
                  <div class="switch-row" style="cursor:pointer" data-act="open-project" data-id="${esc(p.id)}">
                    <div class="row" style="min-width:0">
                      <div style="width:52px;height:32px;border-radius:6px;overflow:hidden;background:#0a0c12;flex-shrink:0;display:grid;place-items:center">
                        ${p.thumbnail_url ? `<img src="${esc(p.thumbnail_url)}" style="width:100%;height:100%;object-fit:cover" />` : svg("film", 14)}
                      </div>
                      <div style="min-width:0">
                        <div class="switch-row-title">${esc(p.name)}</div>
                        <div class="switch-row-desc">${p.shot_count} shots · Updated ${fmtDate(p.updated_at)}</div>
                      </div>
                    </div>
                    <div class="row">
                      ${p.overall_virality ? `<span class="badge ${scoreClass(p.overall_virality)}">${p.overall_virality}/100</span>` : ""}
                      <button class="btn btn-sm" data-act="open-project" data-id="${esc(p.id)}">Open</button>
                    </div>
                  </div>
                `).join("")}
              </div>
            `}
          </div>

          <div class="panel">
            <div class="panel-header">
              <h2 class="panel-title">${svg("cpu", 15)} Recent Processing Activity</h2>
              <button class="btn btn-sm" data-nav="analysis">Automation Deck</button>
            </div>
            ${activity.length === 0 ? `
              <div class="empty-state">${svg("sparkles", 26)}<div>Processing events and AI analysis logs appear here.</div></div>
            ` : `
              <div class="log-box" style="max-height:310px">
                ${activity.map(a => `
                  <div class="log-line ${esc(a.level || "info")}">
                    <span class="muted">[${fmtDate(a.ts)}]</span> <strong>${esc(a.project_name || "")}</strong> · [${esc(a.stage)}] ${esc(a.message)}
                  </div>
                `).join("")}
              </div>
            `}
          </div>
        </div>
      </div>
    `;
  }

  function renderProjects(S) {
    const projs = S.projectsList || [];
    const q = (S.projectSearch || "").toLowerCase();
    const filtered = projs.filter(p => !q || (p.name || "").toLowerCase().includes(q));
    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">Projects</h1>
            <p class="page-sub">Local project storage with autosave and interrupted-session recovery</p>
          </div>
          <div class="row">
            <input class="input" style="width:220px" placeholder="Search projects..." value="${esc(S.projectSearch || "")}" data-bind="projectSearch" />
            <button class="btn btn-primary" data-act="new-project">${svg("plus", 14)} New Project</button>
          </div>
        </div>

        ${filtered.length === 0 ? `
          <div class="panel"><div class="empty-state">${svg("folder", 30)}<div>No matching projects found.</div></div></div>
        ` : `
          <div class="grid-3">
            ${filtered.map(p => `
              <div class="project-card">
                <div class="project-thumb" style="cursor:pointer" data-act="open-project" data-id="${esc(p.id)}">
                  ${p.thumbnail_url ? `<img src="${esc(p.thumbnail_url)}" />` : svg("film", 28)}
                  ${p.overall_virality ? `<span class="badge ${scoreClass(p.overall_virality)}" style="position:absolute;top:8px;right:8px">Score ${p.overall_virality}</span>` : ""}
                  ${p.has_recovery ? `<span class="badge score-mod" style="position:absolute;top:8px;left:8px">Recovery Available</span>` : ""}
                </div>
                <div style="padding:12px;display:flex;flex-direction:column;gap:8px;flex:1">
                  <div>
                    <div style="font-weight:600;font-size:13.5px">${esc(p.name)}</div>
                    <div class="muted" style="font-size:11px">${p.media_count} media · ${p.shot_count} shots · ${fmtDate(p.updated_at)}</div>
                  </div>
                  <div class="row wrap" style="margin-top:auto">
                    <button class="btn btn-primary btn-sm" data-act="open-project" data-id="${esc(p.id)}">Open</button>
                    <button class="btn btn-sm" data-act="rename-project" data-id="${esc(p.id)}" title="Rename">${svg("edit", 12)}</button>
                    <button class="btn btn-sm" data-act="duplicate-project" data-id="${esc(p.id)}" title="Duplicate">${svg("copy", 12)}</button>
                    <button class="btn btn-danger btn-sm" data-act="delete-project" data-id="${esc(p.id)}" title="Delete">${svg("trash", 12)}</button>
                  </div>
                </div>
              </div>
            `).join("")}
          </div>
        `}
      </div>
    `;
  }

  function _noProjectBanner() {
    return `
      <div class="scroll-view">
        <div class="panel">
          <div class="empty-state">
            ${svg("film", 34)}
            <div style="font-size:15px;font-weight:600;color:var(--text-0)">No Active Project Open</div>
            <div>Create a new project or import a video file to launch the AgentVid editing workspace.</div>
            <div class="row" style="margin-top:6px">
              <button class="btn" data-act="new-project">${svg("plus", 14)} New Project</button>
              <button class="btn btn-primary" data-act="quick-import">${svg("upload", 14)} Import Video</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function renderEditor(S) {
    const proj = S.project;
    if (!proj) return _noProjectBanner();

    const mediaList = proj.media || [];
    const audioList = proj.audio_tracks || [];
    const activeMedia = mediaList.find(m => m.id === proj.active_media_id) || mediaList[0] || null;
    const shots = proj.shots || [];
    const selShot = shots.find(s => s.id === S.selectedShotId) || shots[0] || null;
    const tab = S.editorRightTab || "shot";
    const ft = proj.face_tracking || {};
    const fcfg = ft.config || S.settings.face_detection || {};
    const tl = proj.timeline || {};
    const capCfg = tl.caption_config || {};

    return `
      <div class="editor-workspace">
        <!-- LEFT PANE: Assets & Shot Library -->
        <div class="ed-left">
          <div class="pane-head">
            <span>${svg("film", 13)} Media &amp; Shots</span>
            <div class="row" style="gap:4px">
              <button class="btn btn-sm" data-act="import-video" title="Import Video">${svg("upload", 12)} Video</button>
              <button class="btn btn-sm" data-act="import-audio" title="Import Background Music">${svg("music", 12)}</button>
            </div>
          </div>
          <div class="pane-body">
            ${proj.has_recovery ? `
              <div class="panel panel-tight" style="margin-bottom:10px;border-color:rgba(251,191,36,0.45)">
                <div style="font-size:11.5px;font-weight:600;color:var(--amber)">Interrupted Session Found</div>
                <div class="muted" style="font-size:11px;margin:4px 0 8px">An autosaved snapshot exists for this project.</div>
                <div class="row">
                  <button class="btn btn-sm btn-primary" data-act="recover-accept">Recover</button>
                  <button class="btn btn-sm" data-act="recover-discard">Discard</button>
                </div>
              </div>
            ` : ""}

            <div class="nav-section-label" style="padding-left:0">Project Media (${mediaList.length})</div>
            ${mediaList.length === 0 ? `
              <div class="muted" style="font-size:11.5px;padding:8px 0">Import a video file to begin.</div>
            ` : mediaList.map(m => `
              <div class="switch-row" style="margin-bottom:6px;cursor:pointer;${activeMedia && activeMedia.id === m.id ? "border-color:rgba(56,189,248,0.45)" : ""}" data-act="select-media" data-id="${esc(m.id)}">
                <div style="min-width:0">
                  <div class="switch-row-title" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(m.name)}</div>
                  <div class="switch-row-desc">${m.width}x${m.height} · ${fmtTime(m.duration)}</div>
                </div>
              </div>
            `).join("")}

            ${audioList.length > 0 ? `
              <div class="nav-section-label" style="padding-left:0;margin-top:8px">Background Audio (${audioList.length})</div>
              <select class="select" data-act="set-bg-music" style="margin-bottom:8px">
                <option value="">No background music</option>
                ${audioList.map(a => `<option value="${esc(a.id)}" ${tl.background_music === a.id ? "selected" : ""}>${esc(a.name)}</option>`).join("")}
              </select>
            ` : ""}

            <div class="row-between" style="margin-top:10px;margin-bottom:6px">
              <span class="nav-section-label" style="padding:0">Extracted Peak Reels (${shots.length})</span>
              ${activeMedia ? `<button class="btn btn-sm" data-act="run-manual-analyze" title="Re-scan video for Peak Reels, Faces &amp; Virality">${svg("sparkles", 11)} Re-Scan</button>` : ""}
            </div>
            ${(proj.analysis && proj.analysis.reel_selection_mode) ? `
              <div class="reel-mode-banner ${proj.analysis.reel_selection_mode === "ai_peak_detection" ? "is-ai" : ""}">
                <div class="row-between" style="margin-bottom:3px">
                  <strong style="color:${proj.analysis.reel_selection_mode === "ai_peak_detection" ? "var(--accent-bright)" : "var(--text-0)"}">
                    ${proj.analysis.reel_selection_mode === "ai_peak_detection" ? `AI Peak Finder (${esc(proj.analysis.ai_model || "API")})` : "Local Peak Detector"}
                  </strong>
                  ${proj.analysis.reel_selection_mode !== "ai_peak_detection" ? `<button class="btn btn-sm" style="padding:1px 6px;font-size:10px" data-nav="settings">Set API Key</button>` : ""}
                </div>
                <div class="muted" style="font-size:10.5px">${esc(proj.analysis.reel_selection_note || "")}</div>
              </div>
            ` : ""}
            <div style="display:flex;flex-direction:column;gap:5px">
              ${shots.map(sh => `
                <div class="switch-row" style="padding:6px 8px;cursor:pointer;${selShot && selShot.id === sh.id ? "border-color:var(--accent);background:rgba(0,102,255,0.12)" : ""}" data-act="select-shot" data-id="${esc(sh.id)}">
                  <div style="min-width:0">
                    <div style="font-size:12px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                      Reel ${String(sh.number).padStart(2, "0")} <span class="muted mono" style="font-weight:400;font-size:10.5px">${fmtTime(sh.trim_start)}–${fmtTime(sh.trim_end)}</span>
                    </div>
                    <div class="muted" style="font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(sh.title || sh.scene_category)} ${sh.face_info && sh.face_info.face_detected ? "· Face" : ""}</div>
                  </div>
                  <span class="badge ${scoreClass(sh.virality && sh.virality.score)}">${(sh.virality && sh.virality.score) || "—"}</span>
                </div>
              `).join("")}
            </div>
          </div>
        </div>

        <!-- CENTER PANE: Video Preview + Crop Mark Overlay + Face Overlay + Draggable Live Caption Preview -->
        <div class="ed-center">
          <div class="monitor-head">
            <div class="monitor-head-top">
              <div class="monitor-head-title">
                ${svg("play", 13)}
                <span>Program Monitor</span>
                ${selShot ? `<span class="badge" style="white-space:nowrap">Reel ${String(selShot.number).padStart(2, "0")}</span>` : ""}
                <span class="badge score-strong" style="white-space:nowrap">${esc(tl.aspect || "9:16")}</span>
              </div>
              <div class="monitor-aspect-wrap">
                <select class="select" data-act="set-timeline-aspect" aria-label="Output Aspect Ratio">
                  <option value="9:16" ${(tl.aspect || "9:16") === "9:16" ? "selected" : ""}>9:16 Vertical</option>
                  <option value="1:1" ${tl.aspect === "1:1" ? "selected" : ""}>1:1 Square</option>
                  <option value="16:9" ${tl.aspect === "16:9" ? "selected" : ""}>16:9 Landscape</option>
                </select>
              </div>
            </div>
            <div class="monitor-head-controls">
              <div class="monitor-toggles">
                <button class="cap-toggle-pill ${capCfg.enabled !== false ? "is-on" : ""}" data-act="toggle-editor-captions" title="Turn Auto-Captions ON or OFF for preview &amp; all exported Reels">
                  <span class="cap-dot"></span>
                  ${svg("type", 12)}
                  <span>Captions ${capCfg.enabled !== false ? "ON" : "OFF"}</span>
                </button>
                <button class="cap-toggle-pill ${S.showReframeGuide ? "is-on" : ""}" data-act="toggle-reframe-guide" title="Show or hide the aspect-ratio render crop frame mark on the video">
                  <span class="cap-dot"></span>
                  ${svg("maximize", 12)}
                  <span>Crop Mark ${S.showReframeGuide ? "ON" : "OFF"}</span>
                </button>
                <button class="cap-toggle-pill ${S.showFaceOverlay ? "is-on" : ""}" data-act="toggle-face-overlay" title="Show or hide face tracking boxes">
                  <span class="cap-dot"></span>
                  ${svg("scan", 12)}
                  <span>Faces ${S.showFaceOverlay ? "ON" : "OFF"}</span>
                </button>
              </div>
              <span class="muted mono" style="font-size:10.5px;white-space:nowrap;flex-shrink:0">${S.showReframeGuide ? "Shaded area = cut on export" : "Crop mark hidden"}</span>
            </div>
          </div>

          <div class="preview-stage">
            ${activeMedia ? `
              <div class="video-frame-wrap" id="video-frame-wrap">
                <video id="studio-video" src="${esc(activeMedia.stream_url)}" preload="metadata" playsinline></video>
                <div class="overlay-layer" id="video-overlay-layer"></div>
                <div id="live-caption-overlay" class="live-caption-box draggable cap-style-${esc(capCfg.style || "liquid_silver")}" data-drag-hint="Drag X/Y · ${Math.round(Number(capCfg.x_offset ?? 50))}% / ${Math.round(Number(capCfg.y_offset ?? 80))}%" title="Drag horizontally or vertically to move caption position" style="display:none;left:${Number(capCfg.x_offset ?? 50)}%;top:${Number(capCfg.y_offset ?? 80)}%;font-family:'${esc(capCfg.font || "Poppins ExtraBold")}', var(--font-sans);color:${esc(capCfg.color || "#FFFFFF")};font-size:${Math.max(12, Math.round((capCfg.font_size || 64) * 0.34))}px"></div>
              </div>
            ` : `
              <div class="empty-state">
                ${svg("upload", 34)}
                <div style="font-size:14px;font-weight:600;color:var(--text-0)">Import Footage to Start Editing</div>
                <div>Supports MP4, MOV, MKV, WebM, AVI with local FFmpeg &amp; OpenCV processing.</div>
                <button class="btn btn-primary" data-act="import-video">${svg("upload", 14)} Import Video File</button>
              </div>
            `}
          </div>

          <div class="transport-bar">
            <div class="row">
              <button class="btn btn-sm btn-primary" data-act="toggle-play" id="btn-play-toggle">${svg("play", 13)} Play</button>
              ${selShot ? `<button class="btn btn-sm" data-act="play-selected-shot">Preview Reel ${String(selShot.number).padStart(2, "0")}</button>` : ""}
              ${selShot ? `<button class="btn btn-sm" data-act="split-at-playhead">${svg("scissors", 12)} Split at Playhead</button>` : ""}
            </div>
            <div class="timecode" id="transport-timecode">00:00.0 / ${fmtTime(activeMedia ? activeMedia.duration : 0)}</div>
          </div>
        </div>

        <!-- RIGHT PANE: Tabbed Inspector (Reel & Captions / Face Tracking / AI Assistant) -->
        <div class="ed-right">
          <div class="tabs">
            <button class="tab-btn ${tab === "shot" ? "active" : ""}" data-act="editor-tab" data-tab="shot">Reel &amp; Captions</button>
            <button class="tab-btn ${tab === "faces" ? "active" : ""}" data-act="editor-tab" data-tab="faces">Face AI</button>
            <button class="tab-btn ${tab === "ai" ? "active" : ""}" data-act="editor-tab" data-tab="ai">Assistant</button>
          </div>
          <div class="pane-body">
            ${tab === "shot" ? _renderShotInspector(selShot, shots, capCfg, S) : tab === "faces" ? _renderFaceInspector(proj, fcfg) : _renderAssistantPane(S)}
          </div>
        </div>

        <!-- BOTTOM PANE: Peak Reels Visual Timeline -->
        <div class="ed-bottom">
          <div class="pane-head">
            <div class="row">
              <span>${svg("scissors", 13)} Peak Reels Timeline</span>
              <span class="muted">${shots.filter(s => (s.edit || {}).included !== false).length} / ${shots.length} Reels active · Captions ${capCfg.enabled !== false ? "ON" : "OFF"}</span>
            </div>
            <div class="row">
              ${shots.length > 0 ? `<button class="btn btn-sm btn-primary" data-act="export-all-timeline-reels">${svg("zap", 12)} Export All ${shots.filter(s => (s.edit || {}).included !== false).length} Reels</button>` : ""}
              ${selShot ? `
                <button class="btn btn-sm" data-act="move-shot-left" title="Move Earlier">${svg("chevLeft", 12)}</button>
                <button class="btn btn-sm" data-act="move-shot-right" title="Move Later">${svg("chevRight", 12)}</button>
                <button class="btn btn-sm" data-act="merge-next-shot" title="Merge with Next">${svg("merge", 12)} Merge</button>
                <button class="btn btn-sm" data-act="export-single-shot" data-id="${esc(selShot.id)}">${svg("download", 12)} Export Reel</button>
              ` : ""}
            </div>
          </div>
          <div class="timeline-track">
            ${shots.length === 0 ? `
              <div class="empty-state" style="width:100%;padding:22px">
                <div>No Peak Reels extracted yet. ${activeMedia ? "Click Re-Scan or enable AUTO mode." : "Submit a link or import a video first."}</div>
              </div>
            ` : shots.map(sh => {
              const inc = (sh.edit || {}).included !== false;
              const vsc = (sh.virality && sh.virality.score) || 0;
              const faceOk = sh.face_info && sh.face_info.face_detected;
              return `
                <div class="tl-shot ${selShot && selShot.id === sh.id ? "selected" : ""} ${inc ? "" : "excluded"}" data-act="select-shot" data-id="${esc(sh.id)}">
                  ${sh.thumbnail_url ? `<img class="tl-thumb" src="${esc(sh.thumbnail_url)}" />` : `<div class="tl-thumb" style="display:grid;place-items:center">${svg("film", 20)}</div>`}
                  <div class="tl-meta">
                    <div class="tl-row">
                      <strong style="font-size:11.5px">REEL ${String(sh.number).padStart(2, "0")}</strong>
                      <span class="badge ${scoreClass(vsc)}">${vsc || "—"}</span>
                    </div>
                    <div class="tl-row muted mono" style="font-size:10px">
                      <span>${fmtTime(sh.trim_start)}–${fmtTime(sh.trim_end)}</span>
                      <span>${Number(sh.duration || 0).toFixed(1)}s</span>
                    </div>
                    <div class="tl-row" style="margin-top:2px">
                      <span class="badge" style="font-size:9.5px;max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${faceOk ? `${svg("user", 10)} Face` : esc(sh.scene_category)}</span>
                      <button class="btn btn-sm" style="padding:2px 6px;font-size:10px" data-act="toggle-shot-include" data-id="${esc(sh.id)}" title="${inc ? "Exclude from export" : "Include in export"}">
                        ${inc ? svg("eye", 11) : svg("eyeOff", 11)}
                      </button>
                    </div>
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        </div>
      </div>
    `;
  }

  function _renderShotInspector(sh, shots, capCfg = {}, S = {}) {
    const capOn = capCfg.enabled !== false;
    const capX = Math.round(Number(capCfg.x_offset ?? 50));
    const capY = Math.round(Number(capCfg.y_offset ?? 80));
    const capSize = Math.round(Number(capCfg.font_size || 64));
    const capLang = capCfg.language || "auto";
    const langs = (S.captionLanguages && S.captionLanguages.length) ? S.captionLanguages : [
      { id: "auto", label: "Auto-Detect Spoken Language" },
      { id: "en", label: "English" },
      { id: "hi-Latn", label: "Hinglish (Hindi in English letters)" },
      { id: "hi", label: "Hindi (हिन्दी)" },
    ];
    const cuesCount = ((S.project && S.project.timeline && S.project.timeline.captions) || []).length;
    const capNote = (S.project && S.project.analysis && S.project.analysis.caption_note) || "";
    const genBusy = !!S.captionGenBusy;

    const capQuickPanel = `
      <div class="panel panel-tight" style="margin-bottom:12px;border-color:${capOn ? "rgba(0,102,255,0.42)" : "var(--border)"};background:var(--bg-0)">
        <div class="row-between" style="margin-bottom:8px">
          <strong style="font-size:12px">${svg("type", 13)} Auto-Captions &amp; Placement</strong>
          <div class="switch ${capOn ? "on" : ""}" data-act="toggle-editor-captions"></div>
        </div>
        ${capOn ? `
          <div class="field" style="margin-bottom:8px">
            <label><span>Caption Language</span><span class="mono">${cuesCount} cues</span></label>
            <select class="select" data-cap-cfg="language">
              ${langs.map(l => `<option value="${esc(l.id)}" ${capLang === l.id ? "selected" : ""}>${esc(l.label)}</option>`).join("")}
            </select>
          </div>
          <div class="row" style="gap:6px;margin-bottom:10px">
            <button class="btn btn-primary btn-sm" style="flex:1" data-act="generate-captions-now" ${genBusy ? "disabled" : ""}>
              ${genBusy ? `${svg("loader", 12, "spin")} Listening &amp; Syncing...` : `${svg("sparkles", 12)} Generate Voice Captions`}
            </button>
          </div>
          ${capNote ? `<div class="muted" style="font-size:10.5px;margin-bottom:8px;line-height:1.4">${esc(capNote)}</div>` : ""}

          <div class="muted" style="font-size:10.5px;margin-bottom:8px">
            Drag the caption <strong>horizontally or vertically</strong> on the video preview, or adjust sliders below:
          </div>

          <div class="field" style="margin-bottom:8px">
            <label><span>Caption Size</span><span class="mono" id="editor-cap-size-label">${capSize}px</span></label>
            <input type="range" id="editor-cap-size-slider" min="28" max="120" step="2" value="${capSize}" data-cap-cfg="font_size" />
          </div>

          <div class="field" style="margin-bottom:6px">
            <label><span>Horizontal Position (X)</span><span class="mono" id="editor-cap-x-label">${capX}%</span></label>
            <input type="range" id="editor-cap-x-slider" min="10" max="90" step="1" value="${capX}" data-cap-cfg="x_offset" />
          </div>
          <div class="row wrap" style="gap:5px;margin-bottom:10px">
            ${[["Left", 25], ["Center", 50], ["Right", 75]].map(([lbl, xv]) => `
              <button class="chip-btn ${Math.abs(capX - xv) <= 4 ? "active" : ""}" style="padding:3px 9px;font-size:10.5px" data-act="set-cap-x-snap" data-x="${xv}">${lbl}</button>
            `).join("")}
          </div>

          <div class="field" style="margin-bottom:6px">
            <label><span>Vertical Position (Y)</span><span class="mono" id="editor-cap-y-label">${capY}%</span></label>
            <input type="range" id="editor-cap-y-slider" min="10" max="90" step="1" value="${capY}" data-cap-cfg="y_offset" />
          </div>
          <div class="row wrap" style="gap:5px;margin-bottom:10px">
            ${[["Top", 18, "top"], ["Center", 50, "center"], ["Lower", 72, "bottom"], ["Bottom", 82, "bottom"]].map(([lbl, yv, pos]) => `
              <button class="chip-btn ${Math.abs(capY - yv) <= 4 ? "active" : ""}" style="padding:3px 9px;font-size:10.5px" data-act="set-cap-pos-snap" data-y="${yv}" data-pos="${pos}">${lbl}</button>
            `).join("")}
          </div>

          <div class="row-between" style="gap:6px">
            <span class="muted" style="font-size:10.5px">Style: <strong style="color:var(--text-0)">${esc(capCfg.style || "liquid_silver")}</strong></span>
            <button class="btn btn-sm" data-nav="captions">${svg("sparkles", 11)} Style &amp; Fonts →</button>
          </div>
        ` : `
          <div class="muted" style="font-size:11px">Auto-captions are OFF. Exported Reels will render clean without subtitles.</div>
        `}
      </div>
    `;
    if (!sh) return `${capQuickPanel}<div class="empty-state">Select a Reel on the timeline to inspect virality breakdown and apply edits.</div>`;
    const ed = sh.edit || {};
    const vir = sh.virality || {};
    const dims = vir.dimensions || {};
    const sug = sh.suggestions || {};
    return `
      ${capQuickPanel}
      <div class="row-between" style="margin-bottom:8px">
        <div>
          <strong style="font-size:14px">REEL ${String(sh.number).padStart(2, "0")}</strong>
          <span class="muted mono" style="margin-left:6px;font-size:11px">${fmtTime(sh.trim_start)}–${fmtTime(sh.trim_end)} (${sh.duration}s)</span>
        </div>
        <span class="badge ${scoreClass(vir.score)}">Virality ${vir.score || 0}/100</span>
      </div>
      ${sh.hook ? `<div class="badge score-strong" style="margin-bottom:6px">HOOK: ${esc(sh.hook)}</div>` : ""}
      ${sh.title ? `<div style="font-size:12.5px;font-weight:600;margin-bottom:5px;color:var(--text-0)">${esc(sh.title)}</div>` : ""}

      <p class="muted" style="font-size:11.5px;margin:0 0 10px">${esc(sh.description)}</p>
      <div class="muted" style="font-size:11px;margin-bottom:10px"><strong>Audio:</strong> ${esc(sh.audio_observation || "—")}</div>

      ${vir.recommendation ? `
        <div class="panel panel-tight" style="margin-bottom:10px;border-color:rgba(56,189,248,0.28)">
          <div style="font-size:11px;font-weight:600;color:var(--cyan);margin-bottom:4px">AI Recommendation (${esc(vir.confidence || "Local")})</div>
          <div style="font-size:11.5px">${esc(vir.recommendation)}</div>
          <div class="row wrap" style="margin-top:8px">
            ${sug.zoom ? `<button class="btn btn-sm" data-act="apply-suggestion" data-id="${esc(sh.id)}" data-sug="apply_zoom">Apply Zoom (${sug.zoom.recommended_zoom}x)</button>` : ""}
            ${sug.reframing ? `<button class="btn btn-sm" data-act="apply-suggestion" data-id="${esc(sh.id)}" data-sug="apply_reframe">Apply Smart Reframe</button>` : ""}
            <button class="btn btn-sm" data-act="apply-suggestion" data-id="${esc(sh.id)}" data-sug="trim_silence">Trim Silence</button>
          </div>
        </div>
      ` : ""}

      <div class="nav-section-label" style="padding-left:0">Non-Destructive Controls</div>
      <div class="grid-2" style="gap:8px">
        <div class="field"><label>Trim Start (s)</label><input class="input mono" type="number" step="0.1" value="${sh.trim_start}" data-shot-edit="trim_start" data-id="${esc(sh.id)}" /></div>
        <div class="field"><label>Trim End (s)</label><input class="input mono" type="number" step="0.1" value="${sh.trim_end}" data-shot-edit="trim_end" data-id="${esc(sh.id)}" /></div>
      </div>

      <div class="field">
        <label><span>Playback Speed</span><span class="mono">${ed.speed || 1.0}x</span></label>
        <input type="range" min="0.25" max="3.0" step="0.05" value="${ed.speed || 1.0}" data-shot-edit="speed" data-id="${esc(sh.id)}" />
      </div>
      <div class="field">
        <label><span>Zoom</span><span class="mono">${ed.zoom || 1.0}x</span></label>
        <input type="range" min="1.0" max="2.5" step="0.05" value="${ed.zoom || 1.0}" data-shot-edit="zoom" data-id="${esc(sh.id)}" />
      </div>
      <div class="grid-2" style="gap:8px">
        <div class="field"><label><span>Pan X</span><span class="mono">${Math.round((ed.pan_x ?? 0.5) * 100)}%</span></label><input type="range" min="0" max="1" step="0.02" value="${ed.pan_x ?? 0.5}" data-shot-edit="pan_x" data-id="${esc(sh.id)}" /></div>
        <div class="field"><label><span>Pan Y</span><span class="mono">${Math.round((ed.pan_y ?? 0.5) * 100)}%</span></label><input type="range" min="0" max="1" step="0.02" value="${ed.pan_y ?? 0.5}" data-shot-edit="pan_y" data-id="${esc(sh.id)}" /></div>
      </div>
      <div class="field">
        <label><span>Audio Gain</span><span class="mono">${ed.muted ? "MUTED" : Math.round((ed.volume ?? 1.0) * 100) + "%"}</span></label>
        <input type="range" min="0" max="2" step="0.05" value="${ed.volume ?? 1.0}" data-shot-edit="volume" data-id="${esc(sh.id)}" />
      </div>
      <div class="field">
        <label>Transition In</label>
        <select class="select" data-shot-edit="transition" data-id="${esc(sh.id)}">
          ${["none", "fade", "dissolve", "wipeleft", "wiperight", "slideup", "zoomin"].map(t => `<option value="${t}" ${(ed.transition || "none") === t ? "selected" : ""}>${t}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label>Shot Text Overlay</label>
        <input class="input" placeholder="Optional headline overlay for this shot..." value="${esc(ed.text_overlay || "")}" data-shot-edit="text_overlay" data-id="${esc(sh.id)}" />
      </div>

      ${Object.keys(dims).length > 0 ? `
        <div class="nav-section-label" style="padding-left:0;margin-top:8px">Key Virality Metrics</div>
        ${[["opening_hook", "Hook"], ["visual_engagement", "Visual"], ["emotional_impact", "Emotional"], ["audio_clarity", "Audio"], ["subject_visibility", "Subject"], ["storytelling", "Story"]].map(([k, lbl]) => `
          <div class="dim-row" style="grid-template-columns:80px 1fr 28px">
            <span class="muted">${lbl}</span>
            <div class="progress-bar"><div class="progress-fill" style="width:${dims[k] || 0}%"></div></div>
            <span class="mono">${dims[k] || 0}</span>
          </div>
        `).join("")}
      ` : ""}
    `;
  }

  function _renderFaceInspector(proj, fcfg) {
    const ft = proj.face_tracking || {};
    const subjects = ft.subjects || [];
    const reframes = ft.reframing_suggestions || {};
    return `
      <div class="row-between" style="margin-bottom:10px">
        <strong>AI Face Detection</strong>
        <div class="switch ${fcfg.enabled ? "on" : ""}" data-act="face-toggle" data-field="enabled"></div>
      </div>

      <div class="field">
        <label>Detection Mode</label>
        <select class="select" data-face-cfg="mode">
          <option value="auto" ${fcfg.mode === "auto" ? "selected" : ""}>Auto on Analysis</option>
          <option value="manual" ${fcfg.mode === "manual" ? "selected" : ""}>Manual Trigger Only</option>
        </select>
      </div>
      <div class="field">
        <label><span>Sensitivity</span><span class="mono">${Math.round((fcfg.sensitivity || 0.65) * 100)}%</span></label>
        <input type="range" min="0.1" max="1.0" step="0.05" value="${fcfg.sensitivity || 0.65}" data-face-cfg="sensitivity" />
      </div>
      <div class="field">
        <label><span>Min Face Size</span><span class="mono">${fcfg.min_face_size || 36}px</span></label>
        <input type="range" min="16" max="160" step="4" value="${fcfg.min_face_size || 36}" data-face-cfg="min_face_size" />
      </div>
      <div class="switch-row" style="margin-bottom:10px">
        <span class="switch-row-title" style="font-size:12px">Multi-Face Support</span>
        <div class="switch ${fcfg.multi_face !== false ? "on" : ""}" data-act="face-toggle" data-field="multi_face"></div>
      </div>

      <div class="row" style="margin-bottom:12px">
        <button class="btn btn-primary btn-sm" style="flex:1" data-act="run-face-detection">${svg("scan", 12)} Run Face Scan</button>
        <button class="btn btn-sm" data-act="reset-face-tracking">${svg("refresh", 12)} Reset</button>
      </div>

      <div class="nav-section-label" style="padding-left:0">Tracked Subjects (${subjects.length})</div>
      <div class="muted" style="font-size:10.5px;margin-bottom:6px">Model: ${esc(ft.model || "OpenCV Local Detector")} · Verified CV detections</div>
      ${subjects.length === 0 ? `<div class="muted" style="font-size:11.5px;margin-bottom:10px">No faces detected yet. Run Face Scan to track subjects.</div>` : subjects.map(s => `
        <div class="switch-row" style="margin-bottom:6px;${ft.primary_subject_id === s.subject_id ? "border-color:var(--emerald)" : ""}">
          <div>
            <div class="switch-row-title">${esc(s.label)} ${ft.primary_subject_id === s.subject_id ? `<span class="badge score-high">Primary</span>` : ""}</div>
            <div class="switch-row-desc">Vis ${Math.round(s.visibility_ratio * 100)}% · Conf ${Math.round(s.avg_confidence * 100)}% · In/Out ${s.entries}/${s.exits}</div>
          </div>
          <button class="btn btn-sm" data-act="set-primary-subject" data-sid="${s.subject_id}">Focus</button>
        </div>
      `).join("")}

      ${Object.keys(reframes).length > 0 ? `
        <div class="nav-section-label" style="padding-left:0;margin-top:8px">Smart Reframing Suggestions</div>
        ${["9:16", "1:1", "16:9"].map(asp => {
          const rf = reframes[asp];
          return rf ? `
            <div class="switch-row" style="margin-bottom:5px">
              <div>
                <div class="switch-row-title">${asp} Framing</div>
                <div class="switch-row-desc">Center (${Math.round(rf.pan_x * 100)}%, ${Math.round(rf.pan_y * 100)}%)</div>
              </div>
              <button class="btn btn-sm" data-act="apply-global-reframe" data-aspect="${asp}">Apply</button>
            </div>
          ` : "";
        }).join("")}
      ` : ""}
    `;
  }

  function _renderAssistantPane(S) {
    const msgs = S.assistantMessages || [];
    return `
      <div class="muted" style="font-size:11px;margin-bottom:8px">
        Grounded in real analyzed shots, virality metrics, and verified transcripts. Never fabricates footage.
      </div>
      <div class="row wrap" style="gap:5px;margin-bottom:10px">
        <button class="btn btn-sm" data-act="ai-quick" data-q="strongest_moments">Best Clips</button>
        <button class="btn btn-sm" data-act="ai-quick" data-q="improve_hooks">Improve Hook</button>
        <button class="btn btn-sm" data-act="ai-quick" data-q="trim_unnecessary">Cut Dead Air</button>
        <button class="btn btn-sm" data-act="ai-quick" data-q="titles_captions">Titles &amp; Captions</button>
        <button class="btn btn-sm" data-act="ai-quick" data-q="broll_style">Style &amp; B-Roll</button>
      </div>
      <div class="chat-messages" id="ai-chat-box">
        ${msgs.length === 0 ? `<div class="chat-msg ai">Ask AgentVid AI Assistant to evaluate your shots, suggest clip sequences, tighten pacing, or plan platform versions.</div>` : msgs.map(m => `
          <div class="chat-msg ${m.role}">${esc(m.text)}${m.meta ? `<div class="muted" style="font-size:10px;margin-top:4px">${esc(m.meta)}</div>` : ""}</div>
        `).join("")}
      </div>
      <div class="row">
        <input class="input" id="ai-chat-input" placeholder="Ask about your shots, hooks, pacing..." />
        <button class="btn btn-primary btn-icon" data-act="ai-send" title="Send">${svg("send", 14)}</button>
      </div>
    `;
  }

  function renderAnalysis(S) {
    const st = S.settings || {};
    const sw = st.automation || {};
    const autoOn = !!st.auto_mode;
    const run = S.automationStatus || { state: "idle", progress: 0, operation: "" };
    const proj = S.project;
    const plan = (proj && proj.analysis && proj.analysis.editing_plan) || [];

    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">AI Analysis &amp; Automation Engine</h1>
            <p class="page-sub">Control AUTO / MANUAL processing and individual AI analysis modules</p>
          </div>
          <div class="row">
            ${proj ? `
              ${run.state === "running" ? `<button class="btn" data-act="auto-pause">${svg("pause", 13)} Pause</button>` : ""}
              ${run.state === "paused" ? `<button class="btn btn-primary" data-act="auto-resume">${svg("play", 13)} Resume</button>` : ""}
              ${(run.state === "running" || run.state === "paused") ? `<button class="btn btn-danger" data-act="auto-stop">${svg("square", 13)} Stop</button>` : `
                <button class="btn btn-primary" data-act="run-full-pipeline">${svg("sparkles", 14)} Run Enabled Pipeline</button>
              `}
            ` : ""}
          </div>
        </div>

        <div class="panel" style="margin-bottom:14px;${autoOn ? "border-color:rgba(56,189,248,0.45)" : ""}">
          <div class="row-between">
            <div>
              <div style="font-size:14px;font-weight:650">Master Mode: ${autoOn ? `<span style="color:var(--cyan)">AUTO MODE ACTIVE</span>` : `<span>MANUAL MODE</span>`}</div>
              <div class="muted" style="font-size:12px;margin-top:2px">
                ${autoOn
                  ? "Imported videos automatically run every enabled automation switch below. Toggling AUTO never alters your saved switches."
                  : "No automatic operations run on import. Use the manual action buttons to trigger individual analyses on demand."}
              </div>
            </div>
            <div class="switch ${autoOn ? "on" : ""}" data-act="toggle-auto-mode"></div>
          </div>

          ${proj ? `
            <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border)">
              <div class="row-between" style="margin-bottom:6px">
                <span style="font-size:12px">Status: <strong>${esc(run.state || "idle").toUpperCase()}</strong> ${run.operation ? `— ${esc(run.operation)}` : ""}</span>
                <span class="mono" style="font-size:12px">${Math.round((run.progress || 0) * 100)}%</span>
              </div>
              <div class="progress-bar"><div class="progress-fill" style="width:${Math.round((run.progress || 0) * 100)}%"></div></div>
              <div class="row wrap" style="margin-top:10px">
                <button class="btn btn-sm" data-act="run-manual-task" data-task="scene_detection">Run Scene &amp; Shot Detection</button>
                <button class="btn btn-sm" data-act="run-manual-task" data-task="face_detection">Run Face Detection &amp; Tracking</button>
                <button class="btn btn-sm" data-act="run-manual-task" data-task="virality_scoring">Compute Virality Scores</button>
                <button class="btn btn-sm" data-act="extract-local-captions">Extract Local Captions</button>
              </div>
            </div>
          ` : ""}
        </div>

        <div class="panel" style="margin-bottom:14px">
          <div class="panel-header">
            <h2 class="panel-title">${svg("cpu", 15)} Individual Automation Switches (14 Controls)</h2>
            <span class="muted" style="font-size:11px">Persisted independently of AUTO/MANUAL toggle</span>
          </div>
          <div class="grid-2" style="gap:8px">
            ${AUTOMATION_META.map(([key, title, desc]) => `
              <div class="switch-row">
                <div>
                  <div class="switch-row-title">${esc(title)}</div>
                  <div class="switch-row-desc">${esc(desc)}</div>
                </div>
                <div class="switch ${sw[key] ? "on" : ""}" data-act="toggle-auto-switch" data-key="${key}"></div>
              </div>
            `).join("")}
          </div>
        </div>

        ${proj ? `
          <div class="grid-2">
            <div class="panel">
              <div class="panel-header"><h2 class="panel-title">${svg("sparkles", 15)} Editing Plan Recommendations (${plan.length})</h2></div>
              ${plan.length === 0 ? `<div class="muted">Run analysis to generate an approval-based editing plan.</div>` : `
                <div style="display:flex;flex-direction:column;gap:6px;max-height:240px;overflow-y:auto">
                  ${plan.map(item => `
                    <div class="switch-row">
                      <div>
                        <div class="switch-row-title">${esc(item.summary)}</div>
                        <div class="switch-row-desc">Priority: ${esc(item.priority)} · ${item.approved ? "Applied" : "Pending approval"}</div>
                      </div>
                      <button class="btn btn-sm ${item.approved ? "" : "btn-primary"}" data-act="apply-suggestion" data-id="${esc(item.shot_id)}" data-sug="${esc(item.action)}">${item.approved ? "Applied" : "Approve"}</button>
                    </div>
                  `).join("")}
                </div>
              `}
            </div>
            <div class="panel">
              <div class="panel-header"><h2 class="panel-title">${svg("film", 15)} Project Activity Log</h2></div>
              <div class="log-box" style="max-height:240px">
                ${(proj.activity_log || []).slice().reverse().map(ev => `
                  <div class="log-line ${esc(ev.level || "info")}">
                    <span class="muted">[${fmtDate(ev.ts)}]</span> [${esc(ev.stage)}] ${esc(ev.message)}
                  </div>
                `).join("")}
              </div>
            </div>
          </div>
        ` : ""}
      </div>
    `;
  }

  function renderShotLibrary(S) {
    const proj = S.project;
    if (!proj) return _noProjectBanner();
    const shots = proj.shots || [];
    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">Shot Library</h1>
            <p class="page-sub">${shots.length} analyzed shots in "${esc(proj.name)}"</p>
          </div>
          <div class="row">
            <button class="btn" data-act="run-manual-task" data-task="scene_detection">${svg("refresh", 13)} Re-Segment Shots</button>
            <button class="btn btn-primary" data-nav="editor">${svg("scissors", 13)} Open in Editor</button>
          </div>
        </div>
        ${shots.length === 0 ? `<div class="panel"><div class="empty-state">${svg("grid", 28)}<div>No shots analyzed yet.</div></div></div>` : `
          <div class="grid-3">
            ${shots.map(sh => {
              const v = sh.virality || {};
              const f = sh.face_info || {};
              return `
                <div class="project-card">
                  <div class="project-thumb">
                    ${sh.thumbnail_url ? `<img src="${esc(sh.thumbnail_url)}" />` : svg("film", 24)}
                    <span class="badge ${scoreClass(v.score)}" style="position:absolute;top:8px;right:8px">${v.score || 0}/100</span>
                    <span class="badge" style="position:absolute;bottom:8px;left:8px">SHOT ${String(sh.number).padStart(2, "0")} · ${sh.duration}s</span>
                  </div>
                  <div style="padding:12px;display:flex;flex-direction:column;gap:6px;flex:1">
                    <div class="row-between">
                      <span class="badge">${esc(sh.scene_category)}</span>
                      <span class="muted mono" style="font-size:11px">${fmtTime(sh.start)}–${fmtTime(sh.end)}</span>
                    </div>
                    <div style="font-size:12px;color:var(--text-1)">${esc(sh.description)}</div>
                    <div class="muted" style="font-size:11px">${f.face_detected ? `Faces: ${f.face_count} (${Math.round((f.visibility_ratio || 0) * 100)}% visible, conf ${Math.round((f.avg_confidence || 0) * 100)}%)` : "No face detected"}</div>
                    <div class="muted" style="font-size:11px">${esc(sh.audio_observation || "")}</div>
                    <div class="row" style="margin-top:auto;padding-top:6px">
                      <button class="btn btn-sm btn-primary" data-act="inspect-in-editor" data-id="${esc(sh.id)}">Edit Shot</button>
                      <button class="btn btn-sm" data-act="export-single-shot" data-id="${esc(sh.id)}">${svg("download", 12)} Export</button>
                    </div>
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        `}
      </div>
    `;
  }

  function renderVirality(S) {
    const proj = S.project;
    if (!proj) return _noProjectBanner();
    const v = proj.virality || {};
    const allShots = proj.shots || [];
    const byId = Object.fromEntries(allShots.map(s => [s.id, s]));
    const minSc = Number(S.viralityFilterMin ?? 0);
    const maxSc = Number(S.viralityFilterMax ?? 100);
    const sortBy = S.viralitySort || "score_desc";

    const filtered = allShots.filter(s => {
      const sc = (s.virality && s.virality.score) || 0;
      return sc >= minSc && sc <= maxSc;
    });

    filtered.sort((a, b) => {
      const sa = (a.virality && a.virality.score) || 0;
      const sb = (b.virality && b.virality.score) || 0;
      if (sortBy === "score_asc") return sa - sb;
      if (sortBy === "duration_desc") return (b.duration || 0) - (a.duration || 0);
      if (sortBy === "timestamp") return (a.start || 0) - (b.start || 0);
      if (sortBy === "face_visibility") return ((b.face_info || {}).visibility_ratio || 0) - ((a.face_info || {}).visibility_ratio || 0);
      if (sortBy === "hook_strength") return (((b.virality || {}).dimensions || {}).opening_hook || 0) - (((a.virality || {}).dimensions || {}).opening_hook || 0);
      return sb - sa;
    });

    const activeShot = byId[S.selectedShotId] || filtered[0] || allShots[0] || null;
    const dims = (activeShot && activeShot.virality && activeShot.virality.dimensions) || {};
    const labels = (activeShot && activeShot.virality && activeShot.virality.dimension_labels) || (S.viralityLabels || {});

    const chartW = Math.max(460, allShots.length * 46);
    const chartSvg = allShots.length ? `
      <div style="overflow-x:auto">
        <svg width="${chartW}" height="150" viewBox="0 0 ${chartW} 150">
          ${allShots.map((s, idx) => {
            const sc = (s.virality && s.virality.score) || 0;
            const h = Math.max(8, Math.round((sc / 100) * 105));
            const x = 14 + idx * 44;
            const y = 122 - h;
            const fill = sc >= 90 ? "#34d399" : sc >= 75 ? "#38bdf8" : sc >= 60 ? "#fbbf24" : "#fb7185";
            return `
              <g style="cursor:pointer" data-act="select-shot" data-id="${esc(s.id)}">
                <rect x="${x}" y="${y}" width="28" height="${h}" rx="5" fill="${fill}" fill-opacity="${activeShot && activeShot.id === s.id ? "1" : "0.72"}" />
                <text x="${x + 14}" y="${y - 5}" fill="#e2e8f0" font-size="10" text-anchor="middle" font-family="monospace">${sc}</text>
                <text x="${x + 14}" y="140" fill="#94a3b8" font-size="10" text-anchor="middle" font-family="monospace">S${String(s.number).padStart(2, "0")}</text>
              </g>
            `;
          }).join("")}
        </svg>
      </div>
    ` : `<div class="muted">No scored shots yet.</div>`;

    const labelOf = id => byId[id] ? `Shot ${String(byId[id].number).padStart(2, "0")} (${(byId[id].virality || {}).score || 0})` : "—";

    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">Virality Studio</h1>
            <p class="page-sub">15-dimension analytical prediction model — never guaranteed views, always transparent criteria</p>
          </div>
          <div class="row">
            <button class="btn" data-act="run-manual-task" data-task="virality_scoring">${svg("refresh", 13)} Recalculate Scores</button>
            ${(v.recommended_sequence || []).length ? `<button class="btn btn-primary" data-act="apply-recommended-seq">${svg("sparkles", 13)} Apply Best Sequence</button>` : ""}
          </div>
        </div>

        <div class="grid-4" style="margin-bottom:14px">
          <div class="stat-card"><div class="stat-label">Overall Video Score</div><div class="stat-value" style="color:var(--cyan)">${v.overall_score || 0}<span style="font-size:13px;color:var(--text-2)">/100</span></div><div class="stat-sub">${esc(v.overall_tier || "Unscored")}</div></div>
          <div class="stat-card"><div class="stat-label">Average Shot Score</div><div class="stat-value">${v.average_shot_score || 0}</div><div class="stat-sub">Highest: ${labelOf(v.highest_shot_id)} · Lowest: ${labelOf(v.lowest_shot_id)}</div></div>
          <div class="stat-card"><div class="stat-label">Best Opening Hook</div><div class="stat-value" style="font-size:18px">${labelOf(v.best_hook_shot_id)}</div><div class="stat-sub">Emotional Peak: ${labelOf(v.best_emotional_shot_id)}</div></div>
          <div class="stat-card"><div class="stat-label">Best Standalone Clip</div><div class="stat-value" style="font-size:18px">${labelOf(v.best_standalone_shot_id)}</div><div class="stat-sub">${(v.recommended_sequence || []).length} shots in recommended cut</div></div>
        </div>

        <div class="panel" style="margin-bottom:14px">
          <div class="panel-header">
            <h2 class="panel-title">${svg("flame", 15)} Shot-by-Shot Virality Chart</h2>
            <span class="muted" style="font-size:11px">${esc(v.disclaimer || "")}</span>
          </div>
          ${chartSvg}
        </div>

        <div class="grid-2">
          <div class="panel">
            <div class="panel-header">
              <h2 class="panel-title">Ranked Shots (${filtered.length})</h2>
              <div class="row">
                <select class="select" style="width:auto;font-size:11.5px;padding:4px 8px" data-bind="viralitySort">
                  <option value="score_desc" ${sortBy === "score_desc" ? "selected" : ""}>Highest Score</option>
                  <option value="score_asc" ${sortBy === "score_asc" ? "selected" : ""}>Lowest Score</option>
                  <option value="hook_strength" ${sortBy === "hook_strength" ? "selected" : ""}>Hook Strength</option>
                  <option value="face_visibility" ${sortBy === "face_visibility" ? "selected" : ""}>Face Visibility</option>
                  <option value="duration_desc" ${sortBy === "duration_desc" ? "selected" : ""}>Duration</option>
                  <option value="timestamp" ${sortBy === "timestamp" ? "selected" : ""}>Timestamp</option>
                </select>
              </div>
            </div>
            <div class="row" style="margin-bottom:10px;font-size:11.5px">
              <span class="muted">Score Range:</span>
              <input class="input mono" style="width:62px;padding:3px 6px" type="number" min="0" max="100" value="${minSc}" data-bind="viralityFilterMin" />
              <span class="muted">to</span>
              <input class="input mono" style="width:62px;padding:3px 6px" type="number" min="0" max="100" value="${maxSc}" data-bind="viralityFilterMax" />
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;max-height:380px;overflow-y:auto">
              ${filtered.map(s => `
                <div class="switch-row" style="cursor:pointer;${activeShot && activeShot.id === s.id ? "border-color:var(--cyan)" : ""}" data-act="select-shot" data-id="${esc(s.id)}">
                  <div class="row">
                    ${s.thumbnail_url ? `<img src="${esc(s.thumbnail_url)}" style="width:52px;height:32px;border-radius:6px;object-fit:cover" />` : ""}
                    <div>
                      <div class="switch-row-title">SHOT ${String(s.number).padStart(2, "0")} · ${esc(s.scene_category)}</div>
                      <div class="switch-row-desc">${fmtTime(s.start)}–${fmtTime(s.end)} (${s.duration}s) · Hook ${((s.virality || {}).dimensions || {}).opening_hook || 0}</div>
                    </div>
                  </div>
                  <span class="badge ${scoreClass((s.virality || {}).score)}">${(s.virality || {}).score || 0}/100</span>
                </div>
              `).join("")}
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <h2 class="panel-title">${activeShot ? `SHOT ${String(activeShot.number).padStart(2, "0")} — 15-Dimension Breakdown` : "Dimension Breakdown"}</h2>
              ${activeShot ? `<span class="badge ${scoreClass((activeShot.virality || {}).score)}">${(activeShot.virality || {}).score || 0}/100</span>` : ""}
            </div>
            ${activeShot && Object.keys(dims).length ? `
              <p class="muted" style="font-size:12px;margin:0 0 12px">${esc((activeShot.virality || {}).recommendation || "")}</p>
              ${Object.entries(dims).map(([k, val]) => `
                <div class="dim-row">
                  <span class="muted">${esc(labels[k] || k)}</span>
                  <div class="progress-bar"><div class="progress-fill" style="width:${val}%"></div></div>
                  <span class="mono" style="text-align:right">${val}</span>
                </div>
              `).join("")}
            ` : `<div class="muted">Select a scored shot to inspect all 15 weighted dimensions.</div>`}
          </div>
        </div>
      </div>
    `;
  }

  function renderCaptions(S) {
    const proj = S.project;
    if (!proj) return _noProjectBanner();
    const tl = proj.timeline || {};
    const cfg = tl.caption_config || {};
    const cues = tl.captions || [];
    const styles = S.captionStyles || [];
    const anims = S.captionAnimations || [];
    const langs = (S.captionLanguages && S.captionLanguages.length) ? S.captionLanguages : [
      { id: "auto", label: "Auto-Detect Spoken Language" },
      { id: "en", label: "English" },
      { id: "hi-Latn", label: "Hinglish (Hindi in English letters)" },
      { id: "hi", label: "Hindi (हिन्दी)" },
    ];
    const genBusy = !!S.captionGenBusy;
    const fonts = S.fonts && S.fonts.length ? S.fonts : [
      { id: "Poppins-ExtraBold.ttf", family: "Poppins ExtraBold", custom: false },
      { id: "Anton-Regular.ttf", family: "Anton", custom: false },
      { id: "ArchivoBlack-Regular.ttf", family: "Archivo Black", custom: false },
    ];
    const customFonts = fonts.filter(f => f.custom);
    const sampleText = (cues[0] && cues[0].text) || "LIQUID STUDIO CAPTIONS";
    const shaderSwatches = {
      liquid_silver: "linear-gradient(135deg,#fff,#64748b,#1e293b,#e2e8f0)",
      molten_gold: "linear-gradient(135deg,#fef08a,#ca8a04,#713f12,#facc15)",
      glossy_pink: "linear-gradient(135deg,#fff1f7,#ec4899,#831843,#f9a8d4)",
      hyper_gradient: "linear-gradient(135deg,#0066ff,#00e5ff,#ff2e93,#ffae00)",
      cobalt_pulse: "linear-gradient(135deg,#ffffff,#0066ff,#1e3a8a,#60a5fa)",
      solar_plasma: "linear-gradient(135deg,#fef08a,#fb923c,#f43f5e,#c026d3)",
    };
    const specialStyles = styles.filter(st => st.category === "Liquid Metal" || st.category === "Moving Gradients");
    const editorialStyles = styles.filter(st => st.category !== "Liquid Metal" && st.category !== "Moving Gradients");

    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">Kinetic Captions &amp; Text Presets</h1>
            <p class="page-sub">${styles.length} handcrafted presets including Liquid Metal, Moving Gradients, Ultra-Minimal &amp; Custom Fonts</p>
          </div>
          <div class="row wrap">
            ${S.aiAudioReady ? `<span class="badge score-high">${svg("sparkles", 11)} AI Multi-Language Audio Ready</span>` : (S.speechModel && S.speechModel.ready ? `<span class="badge score-high">${svg("check", 11)} Offline English Speech Ready</span>` : `<button class="btn" data-act="open-speech-modal">${svg("download", 13)} Offline Speech Model (${S.speechModel && S.speechModel.doing ? `${S.speechModel.percent}%` : "~480 MB"})</button>`)}
            <button class="btn" data-act="add-caption-cue">${svg("plus", 13)} Add Caption Cue</button>
            <button class="btn btn-primary" data-act="generate-captions-now" ${genBusy ? "disabled" : ""}>
              ${genBusy ? `${svg("loader", 13, "spin")} Transcribing Voices...` : `${svg("sparkles", 13)} Generate Auto-Captions`}
            </button>
          </div>
        </div>

        <div class="grid-2" style="margin-bottom:14px">
          <div class="panel">
            <div class="panel-header">
              <h2 class="panel-title">${svg("type", 15)} Live Style &amp; Motion Preview</h2>
              <div class="row">
                <span class="muted" style="font-size:11px">Burn-In Enabled</span>
                <div class="switch ${cfg.enabled !== false ? "on" : ""}" data-act="cap-toggle" data-field="enabled"></div>
              </div>
            </div>
            <div class="cap-preview-stage">
              <div class="live-caption-box cap-style-${esc(cfg.style || "liquid_silver")}" style="position:relative;left:auto;transform:none;font-family:'${esc(cfg.font || "Poppins ExtraBold")}', var(--font-sans);color:${esc(cfg.color || "#FFFFFF")};font-size:${Math.max(18, Math.round((cfg.font_size || 68) * 0.48))}px;text-transform:${cfg.uppercase ? "uppercase" : "none"};text-shadow:${cfg.shadow !== false ? "0 3px 12px rgba(0,0,0,0.85)" : "none"}">
                ${esc(sampleText).split(" ").map((w, i) => i === 1 ? `<span style="color:${esc(cfg.highlight_color || "#0066FF")}">${w}</span>` : w).join(" ")}
              </div>
              <span class="badge" style="position:absolute;bottom:10px;left:12px">${esc(cfg.style)} · ${esc(cfg.font || "Poppins ExtraBold")}</span>
            </div>

            <div class="nav-section-label" style="padding-left:0;margin-top:14px">Liquid Metal &amp; Animated Moving Gradients (${specialStyles.length})</div>
            <div class="row wrap" style="gap:6px">
              ${specialStyles.map(st => `
                <button class="chip-btn ${cfg.style === st.id ? "active" : ""}" data-act="set-cap-style" data-val="${esc(st.id)}">
                  <span class="chip-swatch" style="background:${shaderSwatches[st.id] || "#fff"}"></span>
                  ${esc(st.label)}
                </button>
              `).join("")}
            </div>

            <div class="nav-section-label" style="padding-left:0;margin-top:12px">Ultra-Minimal, Studio &amp; Creator (${editorialStyles.length})</div>
            <div class="row wrap" style="gap:6px">
              ${editorialStyles.map(st => `
                <button class="chip-btn ${cfg.style === st.id ? "active" : ""}" data-act="set-cap-style" data-val="${esc(st.id)}">${esc(st.label)}</button>
              `).join("")}
            </div>

            <div class="nav-section-label" style="padding-left:0;margin-top:12px">Kinetic Animations (${anims.length})</div>
            <div class="row wrap" style="gap:6px">
              ${anims.map(an => `
                <button class="chip-btn ${cfg.animation === an.id ? "active" : ""}" data-act="set-cap-anim" data-val="${esc(an.id)}">${esc(an.label)}</button>
              `).join("")}
            </div>
          </div>

          <div class="panel">
            <div class="panel-header">
              <h2 class="panel-title">Typography, Custom Fonts &amp; Timing</h2>
              <button class="btn btn-sm" data-act="upload-font">${svg("upload", 12)} Upload Font (.ttf / .otf)</button>
            </div>
            ${customFonts.length ? `
              <div class="row wrap" style="gap:6px;margin-bottom:12px">
                <span class="muted" style="font-size:11px">Your Fonts:</span>
                ${customFonts.map(cf => `
                  <span class="badge" style="gap:6px">
                    ${esc(cf.family)}
                    <button type="button" style="background:none;border:none;color:var(--text-2);cursor:pointer;padding:0;display:grid;place-items:center" data-act="delete-font" data-file="${esc(cf.filename)}" title="Remove font">${svg("x", 11)}</button>
                  </span>
                `).join("")}
              </div>
            ` : ""}
            <div class="grid-2" style="gap:10px">
              <div class="field">
                <label>Caption Language</label>
                <select class="select" data-cap-cfg="language">
                  ${langs.map(l => `<option value="${esc(l.id)}" ${(cfg.language || "auto") === l.id ? "selected" : ""}>${esc(l.label)}</option>`).join("")}
                </select>
              </div>
              <div class="field">
                <label>Font Family</label>
                <select class="select" data-cap-cfg="font">
                  ${fonts.map(fn => `<option value="${esc(fn.family)}" ${cfg.font === fn.family ? "selected" : ""}>${esc(fn.family)}${fn.custom ? " (Custom)" : ""}</option>`).join("")}
                </select>
              </div>
              <div class="field">
                <label><span>Caption Size</span><span class="mono">${cfg.font_size || 64}px</span></label>
                <input type="range" min="28" max="120" step="2" value="${cfg.font_size || 64}" data-cap-cfg="font_size" />
              </div>
              <div class="field">
                <label>Position Zone</label>
                <select class="select" data-cap-cfg="position">
                  <option value="bottom" ${cfg.position === "bottom" ? "selected" : ""}>Bottom Safe Zone</option>
                  <option value="center" ${cfg.position === "center" ? "selected" : ""}>Center Stage</option>
                  <option value="top" ${cfg.position === "top" ? "selected" : ""}>Top Hook Zone</option>
                </select>
              </div>
              <div class="field">
                <label><span>Horizontal Position (X)</span><span class="mono">${Math.round(Number(cfg.x_offset ?? 50))}%</span></label>
                <input type="range" min="10" max="90" step="1" value="${Math.round(Number(cfg.x_offset ?? 50))}" data-cap-cfg="x_offset" />
              </div>
              <div class="field">
                <label><span>Vertical Position (Y)</span><span class="mono">${Math.round(Number(cfg.y_offset ?? 80))}%</span></label>
                <input type="range" min="10" max="90" step="1" value="${Math.round(Number(cfg.y_offset ?? 80))}" data-cap-cfg="y_offset" />
              </div>
              <div class="field"><label>Text Color</label><input type="color" value="${esc(cfg.color || "#FFFFFF")}" data-cap-cfg="color" /></div>
              <div class="field"><label>Highlight Color</label><input type="color" value="${esc(cfg.highlight_color || "#0066FF")}" data-cap-cfg="highlight_color" /></div>
              <div class="field">
                <label>Background Style</label>
                <select class="select" data-cap-cfg="background">
                  ${["none", "glass", "pill", "solid", "subtle"].map(b => `<option value="${b}" ${(cfg.background || "glass") === b ? "selected" : ""}>${b}</option>`).join("")}
                </select>
              </div>
              <div class="field">
                <label><span>Animation Speed</span><span class="mono">${cfg.animation_speed || 1.0}x</span></label>
                <input type="range" min="0.4" max="2.5" step="0.1" value="${cfg.animation_speed || 1.0}" data-cap-cfg="animation_speed" />
              </div>
              <div class="field">
                <label><span>Duration Scale</span><span class="mono">${cfg.duration_scale || 1.0}x</span></label>
                <input type="range" min="0.6" max="1.6" step="0.05" value="${cfg.duration_scale || 1.0}" data-cap-cfg="duration_scale" />
              </div>
              <div class="field">
                <label><span>Word Timing Offset</span><span class="mono">${cfg.word_timing_offset || 0}s</span></label>
                <input type="range" min="-0.5" max="0.5" step="0.05" value="${cfg.word_timing_offset || 0}" data-cap-cfg="word_timing_offset" />
              </div>
            </div>
            <div class="row wrap" style="margin-top:6px">
              <div class="switch-row" style="flex:1"><span class="switch-row-title">Drop Shadow</span><div class="switch ${cfg.shadow !== false ? "on" : ""}" data-act="cap-toggle" data-field="shadow"></div></div>
              <div class="switch-row" style="flex:1"><span class="switch-row-title">ALL CAPS</span><div class="switch ${cfg.uppercase ? "on" : ""}" data-act="cap-toggle" data-field="uppercase"></div></div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h2 class="panel-title">Timed Caption Cues (${cues.length})</h2>
            <span class="muted" style="font-size:11px">Transcript source: ${esc((proj.analysis || {}).transcript_source || "none")}</span>
          </div>
          ${cues.length === 0 ? `<div class="muted">No caption cues yet. Click "Add Caption Cue" to author custom kinetic captions or extract from local speech model.</div>` : `
            <div style="display:flex;flex-direction:column;gap:6px;max-height:260px;overflow-y:auto">
              ${cues.map((c, idx) => `
                <div class="row" style="gap:8px">
                  <input class="input mono" style="width:74px" type="number" step="0.1" value="${c.start}" data-cue-idx="${idx}" data-cue-field="start" />
                  <input class="input mono" style="width:74px" type="number" step="0.1" value="${c.end}" data-cue-idx="${idx}" data-cue-field="end" />
                  <input class="input" style="flex:1" value="${esc(c.text)}" data-cue-idx="${idx}" data-cue-field="text" />
                  <button class="btn btn-danger btn-sm" data-act="del-caption-cue" data-idx="${idx}">${svg("trash", 12)}</button>
                </div>
              `).join("")}
            </div>
          `}
        </div>
      </div>
    `;
  }

  function renderExport(S) {
    const proj = S.project;
    if (!proj) return _noProjectBanner();
    const opts = S.exportOpts || {};
    const job = S.activeExport;
    const est = S.exportEstimate;
    const shots = proj.shots || [];
    const history = (proj.exports || []).slice().reverse();

    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">Export Center</h1>
            <p class="page-sub">Real FFmpeg rendering with H.264 / H.265, GPU acceleration + CPU fallback, burned-in captions &amp; edits</p>
          </div>
          <div class="row">
            ${job && job.status === "running"
              ? `<button class="btn btn-danger" data-act="cancel-export">${svg("square", 13)} Cancel Export</button>`
              : `<button class="btn btn-primary" data-act="start-export">${svg("download", 14)} Start Export</button>`}
          </div>
        </div>

        <div class="panel" style="margin-bottom:14px;border-color:rgba(0,102,255,0.34);background:var(--surface)">
          <div class="row-between wrap" style="gap:12px">
            <div>
              <h2 class="panel-title">${svg("flame", 15)} Batch Export Peak Reels (9:16 Vertical + Face Reframe + Captions)</h2>
              <div class="muted" style="font-size:11.5px;margin-top:3px">
                Exports every extracted Peak Reel as a separate ready-to-post Shorts/Reels MP4 honoring your Auto-Captions ON/OFF, caption position, style &amp; face tracking.
              </div>
            </div>
            <div class="row wrap" style="gap:8px">
              <button class="cap-toggle-pill ${((proj.timeline || {}).caption_config || {}).enabled !== false ? "is-on" : ""}" data-act="toggle-editor-captions">
                <span class="cap-dot"></span>
                <span>Captions ${((proj.timeline || {}).caption_config || {}).enabled !== false ? "ON" : "OFF"}</span>
              </button>
              <select class="select" id="reels-count-sel" style="width:auto;font-size:12px;padding:6px 10px">
                ${Array.from(new Set([shots.filter(s => (s.edit || {}).included !== false).length || 3, 3, 5, 8, 10, 15, 20])).filter(n => n > 0).sort((a, b) => a - b).map(n => `
                  <option value="${n}" ${n === (shots.filter(s => (s.edit || {}).included !== false).length || 3) ? "selected" : ""}>${n} Reels</option>
                `).join("")}
              </select>
              <select class="select" id="reels-dur-sel" style="width:auto;font-size:12px;padding:6px 10px">
                <option value="timeline" selected>Timeline / AI-Picked Lengths</option>
                <option value="15">Fixed 15 sec each</option>
                <option value="30">Fixed 30 sec each</option>
                <option value="45">Fixed 45 sec each</option>
                <option value="60">Fixed 60 sec each</option>
              </select>
              <button class="btn-white-cta" style="padding:7px 14px;font-size:12px" data-act="start-reels-pack" ${job && job.status === "running" ? "disabled" : ""}>${svg("zap", 13)} Export Reels Pack</button>
            </div>
          </div>
          ${job && (job.reels || []).length ? `
            <div style="margin-top:12px;display:flex;flex-direction:column;gap:6px">
              ${job.reels.map(r => `
                <div class="switch-row">
                  <div>
                    <div class="switch-row-title">Reel ${r.index}: ${esc(r.filename)} <span class="badge score-strong">Score ${r.score}</span></div>
                    <div class="switch-row-desc">${fmtTime(r.start)}–${fmtTime(r.end)} (${r.duration}s) · ${r.width}x${r.height} · ${r.actual_mb} MB</div>
                  </div>
                  <div class="row">
                    <a class="btn btn-primary btn-sm" href="${esc(r.file_url)}" download="${esc(r.filename)}">${svg("download", 12)} Save</a>
                    ${window.agentvidDesktop && r.output_path ? `<button class="btn btn-sm" data-act="reveal-path" data-path="${esc(r.output_path)}">Folder</button>` : ""}
                  </div>
                </div>
              `).join("")}
            </div>
          ` : ""}
        </div>

        <div class="grid-2" style="margin-bottom:14px">
          <div class="panel">
            <div class="panel-header"><h2 class="panel-title">${svg("download", 15)} Export Configuration</h2></div>
            <div class="grid-2" style="gap:10px">
              <div class="field">
                <label>Export Scope</label>
                <select class="select" data-exp-opt="mode">
                  <option value="full" ${opts.mode === "full" ? "selected" : ""}>Complete Edited Timeline</option>
                  <option value="shot" ${opts.mode === "shot" ? "selected" : ""}>Individual Shot</option>
                  <option value="top_rated" ${opts.mode === "top_rated" ? "selected" : ""}>Highest-Rated Clips (70+)</option>
                  <option value="social_reels" ${opts.mode === "social_reels" ? "selected" : ""}>Social Media Ready (9:16 Reels/Shorts)</option>
                </select>
              </div>
              ${opts.mode === "shot" ? `
                <div class="field">
                  <label>Select Shot</label>
                  <select class="select" data-exp-opt="shot_id">
                    ${shots.map(s => `<option value="${esc(s.id)}" ${opts.shot_id === s.id ? "selected" : ""}>Shot ${String(s.number).padStart(2, "0")} (${s.duration}s)</option>`).join("")}
                  </select>
                </div>
              ` : `
                <div class="field">
                  <label>Output Filename</label>
                  <input class="input" value="${esc(opts.filename || `${proj.name}_export.mp4`)}" data-exp-opt="filename" />
                </div>
              `}
              <div class="field">
                <label>Video Codec</label>
                <select class="select" data-exp-opt="codec">
                  <option value="h264" ${opts.codec === "h264" ? "selected" : ""}>MP4 · H.264 (Universal)</option>
                  <option value="h265" ${opts.codec === "h265" ? "selected" : ""}>MP4 · H.265 / HEVC (Compact)</option>
                </select>
              </div>
              <div class="field">
                <label>Resolution</label>
                <select class="select" data-exp-opt="resolution">
                  <option value="720p" ${opts.resolution === "720p" ? "selected" : ""}>720p HD</option>
                  <option value="1080p" ${opts.resolution === "1080p" ? "selected" : ""}>1080p Full HD</option>
                  <option value="4k" ${opts.resolution === "4k" ? "selected" : ""}>4K Ultra HD</option>
                </select>
              </div>
              <div class="field">
                <label>Aspect Ratio</label>
                <select class="select" data-exp-opt="aspect">
                  <option value="16:9" ${opts.aspect === "16:9" ? "selected" : ""}>16:9 Landscape</option>
                  <option value="9:16" ${opts.aspect === "9:16" ? "selected" : ""}>9:16 Vertical</option>
                  <option value="1:1" ${opts.aspect === "1:1" ? "selected" : ""}>1:1 Square</option>
                </select>
              </div>
              <div class="field">
                <label>Frame Rate</label>
                <select class="select" data-exp-opt="fps">
                  <option value="24" ${Number(opts.fps) === 24 ? "selected" : ""}>24 fps (Cinema)</option>
                  <option value="30" ${Number(opts.fps) === 30 ? "selected" : ""}>30 fps (Standard)</option>
                  <option value="60" ${Number(opts.fps) === 60 ? "selected" : ""}>60 fps (Smooth)</option>
                </select>
              </div>
              <div class="field">
                <label>Quality Preset</label>
                <select class="select" data-exp-opt="quality">
                  <option value="draft" ${opts.quality === "draft" ? "selected" : ""}>Draft (Fastest)</option>
                  <option value="standard" ${opts.quality === "standard" ? "selected" : ""}>Standard (Balanced)</option>
                  <option value="high" ${opts.quality === "high" ? "selected" : ""}>High Quality</option>
                  <option value="master" ${opts.quality === "master" ? "selected" : ""}>Studio Master</option>
                </select>
              </div>
              <div class="field">
                <label>Audio Bitrate</label>
                <select class="select" data-exp-opt="audio_bitrate">
                  ${["128k", "160k", "192k", "256k", "320k"].map(b => `<option value="${b}" ${opts.audio_bitrate === b ? "selected" : ""}>AAC ${b}</option>`).join("")}
                </select>
              </div>
            </div>
            <div class="field">
              <label>Output Folder</label>
              <div class="row">
                <input class="input mono" style="flex:1" value="${esc(opts.output_dir || "")}" data-exp-opt="output_dir" />
                ${window.agentvidDesktop ? `<button class="btn btn-sm" data-act="pick-export-dir">Browse</button>` : ""}
              </div>
            </div>
            ${est ? `
              <div class="switch-row" style="margin-top:8px">
                <span class="muted">Estimated Output (${est.width}x${est.height}, ${est.shot_count} shots, ${est.duration_sec}s)</span>
                <strong class="mono">~${est.estimated_mb} MB</strong>
              </div>
            ` : ""}
          </div>

          <div class="panel">
            <div class="panel-header"><h2 class="panel-title">Render Progress &amp; Logs</h2></div>
            ${job ? `
              <div class="row-between" style="margin-bottom:6px">
                <span><strong>${esc(job.status).toUpperCase()}</strong> — ${esc(job.stage || "")}</span>
                <span class="mono">${Math.round((job.progress || 0) * 100)}%</span>
              </div>
              <div class="progress-bar" style="margin-bottom:10px"><div class="progress-fill" style="width:${Math.round((job.progress || 0) * 100)}%"></div></div>
              ${job.status === "done" ? `
                <div class="row wrap" style="margin-bottom:10px">
                  <a class="btn btn-primary btn-sm" href="${esc(job.file_url)}" download="${esc(job.filename)}">${svg("download", 12)} Save / Download (${job.actual_mb} MB)</a>
                  ${window.agentvidDesktop ? `<button class="btn btn-sm" data-act="reveal-path" data-path="${esc(job.output_path)}">Show in Folder</button>` : ""}
                </div>
              ` : ""}
              <div class="log-box">${(job.logs || []).map(l => `<div class="log-line">${esc(l)}</div>`).join("")}</div>
            ` : `<div class="empty-state">${svg("download", 26)}<div>Configure your preset and click <strong>Start Export</strong> to render with FFmpeg.</div></div>`}
          </div>
        </div>

        <div class="panel">
          <div class="panel-header"><h2 class="panel-title">Export History (${history.length})</h2></div>
          ${history.length === 0 ? `<div class="muted">No completed exports yet for this project.</div>` : `
            <div style="display:flex;flex-direction:column;gap:6px">
              ${history.map(ex => `
                <div class="switch-row">
                  <div>
                    <div class="switch-row-title">${esc(ex.filename)} <span class="badge">${ex.width}x${ex.height}</span> <span class="badge">${esc((ex.codec || "h264").toUpperCase())}</span></div>
                    <div class="switch-row-desc">${ex.actual_mb || 0} MB · ${ex.duration_sec || 0}s · Encoder: ${esc(ex.encoder || "ffmpeg")} · ${fmtDate(ex.finished_at)}</div>
                  </div>
                  <div class="row">
                    <a class="btn btn-sm" href="${esc(ex.file_url)}" download="${esc(ex.filename)}">${svg("download", 12)}</a>
                    ${window.agentvidDesktop && ex.output_path ? `<button class="btn btn-sm" data-act="reveal-path" data-path="${esc(ex.output_path)}">Folder</button>` : ""}
                  </div>
                </div>
              `).join("")}
            </div>
          `}
        </div>
      </div>
    `;
  }

  function renderSettings(S) {
    const st = S.settings || {};
    const pr = st.privacy || {};
    const pf = st.performance || {};
    const rc = st.reels || { count: 5, duration_mode: "auto_ai", target_duration: 30, min_duration: 18, max_duration: 58, aspect: "9:16", auto_captions: true };
    const cd = st.caption_defaults || { language: "auto", x_offset: 50, y_offset: 80, font_size: 64, position: "bottom", enabled: true };
    const langs = (S.captionLanguages && S.captionLanguages.length) ? S.captionLanguages : [
      { id: "auto", label: "Auto-Detect Spoken Language" },
      { id: "en", label: "English" },
      { id: "hi-Latn", label: "Hinglish (Hindi in English letters)" },
      { id: "hi", label: "Hindi (हिन्दी)" },
    ];
    const aiCfg = S.aiConfig || {};
    const about = S.about || {};

    return `
      <div class="scroll-view">
        <div class="page-header">
          <div>
            <h1 class="page-title">Settings &amp; About AgentVid</h1>
            <p class="page-sub">Peak Reel defaults, AI provider API keys, privacy controls, hardware performance, and studio attribution</p>
          </div>
        </div>

        <!-- PEAK REEL GENERATION DEFAULTS -->
        <div class="panel" style="margin-bottom:14px;border-color:rgba(0,102,255,0.34)">
          <div class="panel-header">
            <h2 class="panel-title">${svg("flame", 15)} Peak Reel Extraction &amp; Shorts Defaults</h2>
            <span class="badge ${aiCfg.ready ? "score-high" : "score-mod"}">${aiCfg.ready ? `AI Peak Finder Active (${esc(aiCfg.provider)})` : "Add AI API Key Below for Deep Podcast Analysis"}</span>
          </div>
          <p class="muted" style="font-size:11.5px;margin-top:0;margin-bottom:14px">
            When you submit a 1-hour podcast or video link, AgentVid scans the entire timeline to extract your chosen number of
            peak moments (never sequential start-to-end slicing) formatted for YouTube Shorts &amp; Instagram Reels.
          </p>

          <div class="grid-2" style="gap:14px;margin-bottom:10px">
            <div>
              <div class="field" style="margin-bottom:8px">
                <label><span>Number of Reels to Generate per Video</span><span class="mono">${rc.count || 5} Reels</span></label>
                <input type="range" min="1" max="20" step="1" value="${rc.count || 5}" data-reel-cfg="count" />
              </div>
              <div class="row wrap" style="gap:6px">
                ${[3, 5, 8, 10, 15, 20].map(n => `
                  <button class="chip-btn ${Number(rc.count || 5) === n ? "active" : ""}" style="padding:4px 10px;font-size:11px" data-act="set-reel-count-chip" data-val="${n}">${n} Reels</button>
                `).join("")}
              </div>
            </div>

            <div>
              <div class="field" style="margin-bottom:8px">
                <label>Reel Duration Mode (Shorts / Reels)</label>
                <select class="select" data-reel-cfg="duration_mode">
                  <option value="auto_ai" ${(rc.duration_mode || "auto_ai") === "auto_ai" ? "selected" : ""}>AI Decides Best Length (18–58s Shorts/Reels)</option>
                  <option value="fixed" ${rc.duration_mode === "fixed" ? "selected" : ""}>Fixed Target Duration (e.g. 30s each)</option>
                </select>
              </div>
              ${rc.duration_mode === "fixed" ? `
                <div class="field" style="margin-bottom:0">
                  <label><span>Fixed Reel Length</span><span class="mono">${rc.target_duration || 30}s</span></label>
                  <input type="range" min="10" max="90" step="5" value="${rc.target_duration || 30}" data-reel-cfg="target_duration" />
                </div>
              ` : `
                <div class="muted" style="font-size:11px;padding:6px 0">
                  AI picks natural standalone hook-to-payoff boundaries between <strong>${rc.min_duration || 18}s</strong> and <strong>${rc.max_duration || 58}s</strong> so every clip fits Shorts &amp; Reels cleanly.
                </div>
              `}
            </div>
          </div>

          <div class="grid-2" style="gap:14px;align-items:center">
            <div class="field" style="margin:0">
              <label>Default Output Aspect Ratio</label>
              <select class="select" data-reel-cfg="aspect">
                <option value="9:16" ${(rc.aspect || "9:16") === "9:16" ? "selected" : ""}>9:16 Vertical (YouTube Shorts / Instagram Reels)</option>
                <option value="1:1" ${rc.aspect === "1:1" ? "selected" : ""}>1:1 Square (Feed)</option>
                <option value="16:9" ${rc.aspect === "16:9" ? "selected" : ""}>16:9 Landscape</option>
              </select>
            </div>
            <div class="switch-row">
              <div>
                <div class="switch-row-title">Auto-Captions Enabled by Default</div>
                <div class="switch-row-desc">Turn captions ON/OFF globally for new videos (also toggleable anytime inside Studio Editor)</div>
              </div>
              <div class="switch ${rc.auto_captions !== false ? "on" : ""}" data-act="toggle-reel-autocaptions"></div>
            </div>
          </div>
        </div>

        <!-- CAPTION DEFAULTS: LANGUAGE, HORIZONTAL/VERTICAL PLACEMENT & SIZE -->
        <div class="panel" style="margin-bottom:14px;border-color:rgba(0,102,255,0.28)">
          <div class="panel-header">
            <h2 class="panel-title">${svg("type", 15)} Caption Defaults · Language, Position (X / Y) &amp; Size</h2>
            ${S.project ? `<button class="btn btn-primary btn-sm" data-act="apply-cap-defaults-project">Apply to Open Project</button>` : `<span class="badge">${S.aiAudioReady ? "AI Multi-Language Audio Ready" : "Add Gemini / Groq / OpenAI Key for Non-English"}</span>`}
          </div>
          <p class="muted" style="font-size:11.5px;margin-top:0;margin-bottom:12px">
            Set the default caption language, horizontal &amp; vertical placement, and font size for all generated Reels.
            For Hindi, Hinglish, Bengali, Urdu, Tamil, or regional languages, connect a <strong>Gemini, Groq, or OpenAI</strong> API key below so AI listens directly to the voices and places dynamic word-synced captions accurately.
          </p>
          <div class="grid-2" style="gap:14px">
            <div class="field">
              <label>Default Spoken / Caption Language</label>
              <select class="select" data-cap-def="language">
                ${langs.map(l => `<option value="${esc(l.id)}" ${(cd.language || "auto") === l.id ? "selected" : ""}>${esc(l.label)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label><span>Caption Size (Smaller ↔ Bigger)</span><span class="mono">${cd.font_size || 64}px</span></label>
              <input type="range" min="28" max="120" step="2" value="${cd.font_size || 64}" data-cap-def="font_size" />
            </div>
            <div>
              <div class="field" style="margin-bottom:6px">
                <label><span>Horizontal Placement (Left ↔ Right)</span><span class="mono">${cd.x_offset ?? 50}%</span></label>
                <input type="range" min="10" max="90" step="1" value="${cd.x_offset ?? 50}" data-cap-def="x_offset" />
              </div>
              <div class="row wrap" style="gap:6px">
                ${[["Left 25%", 25], ["Center 50%", 50], ["Right 75%", 75]].map(([lbl, xv]) => `
                  <button class="chip-btn ${Math.abs((cd.x_offset ?? 50) - xv) <= 4 ? "active" : ""}" style="padding:3px 9px;font-size:11px" data-act="set-cap-def-chip" data-field="x_offset" data-val="${xv}">${lbl}</button>
                `).join("")}
              </div>
            </div>
            <div>
              <div class="field" style="margin-bottom:6px">
                <label><span>Vertical Placement (Top ↔ Bottom)</span><span class="mono">${cd.y_offset ?? 80}%</span></label>
                <input type="range" min="10" max="90" step="1" value="${cd.y_offset ?? 80}" data-cap-def="y_offset" />
              </div>
              <div class="row wrap" style="gap:6px">
                ${[["Top 18%", 18], ["Center 50%", 50], ["Lower 72%", 72], ["Bottom 82%", 82]].map(([lbl, yv]) => `
                  <button class="chip-btn ${Math.abs((cd.y_offset ?? 80) - yv) <= 4 ? "active" : ""}" style="padding:3px 9px;font-size:11px" data-act="set-cap-def-chip" data-field="y_offset" data-val="${yv}">${lbl}</button>
                `).join("")}
              </div>
            </div>
          </div>
        </div>

        <div class="grid-2" style="margin-bottom:14px">
          <div class="panel">
            <div class="panel-header">
              <h2 class="panel-title">${svg("sparkles", 15)} AI Provider API Key (Peak Moment Finder)</h2>
              <span class="badge ${aiCfg.ready ? "score-high" : ""}">${aiCfg.ready ? "Connected" : "No API Key Set"}</span>
            </div>
            <p class="muted" style="font-size:11.5px;margin-top:0">
              Add your Gemini, OpenAI, Groq, Claude, Grok, OpenRouter, or local Ollama key so AgentVid reads the full
              podcast/video transcript and selects the exact peak viral talking moments across the entire episode.
              Face detection, smart 9:16 cropping, and FFmpeg rendering always run 100% locally.
            </p>
            <div class="field">
              <label>Provider</label>
              <select class="select" id="ai-provider-sel">
                ${(aiCfg.providers || []).map(p => `<option value="${esc(p.id)}" ${aiCfg.provider === p.id ? "selected" : ""}>${esc(p.label)}</option>`).join("")}
              </select>
            </div>
            <div class="field">
              <label>Model ID(s) (comma-separated)</label>
              <input class="input mono" id="ai-models-inp" placeholder="e.g. gemini-2.5-flash, gpt-4o-mini, llama3.1" value="${esc((aiCfg.models || []).join(", "))}" />
            </div>
            <div class="field">
              <label>Custom Base URL (optional / Ollama / OpenAI-compatible)</label>
              <input class="input mono" id="ai-url-inp" placeholder="http://127.0.0.1:11434/v1" value="${esc(aiCfg.base_url || "")}" />
            </div>
            <div class="field">
              <label>API Key ${aiCfg.has_key ? `(saved · ends in ${esc(aiCfg.key_hint || "****")})` : "(kept local, never exposed)"}</label>
              <input class="input mono" id="ai-key-inp" type="password" placeholder="Leave blank to keep existing key" />
            </div>
            <div class="row">
              <button class="btn btn-primary btn-sm" data-act="save-ai">Save AI Settings</button>
              <button class="btn btn-sm" data-act="test-ai">Test Connection</button>
            </div>
          </div>

          <div class="panel">
            <div class="panel-header"><h2 class="panel-title">${svg("shield", 15)} Privacy, Security &amp; Performance</h2></div>
            <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px">
              <div class="switch-row">
                <div><div class="switch-row-title">Keep Local Media Local</div><div class="switch-row-desc">All video processing, face tracking, and rendering stay on this PC</div></div>
                <div class="switch ${pr.local_only !== false ? "on" : ""}" data-act="privacy-toggle" data-field="local_only"></div>
              </div>
              <div class="switch-row">
                <div><div class="switch-row-title">Enable Cloud AI Enrichment</div><div class="switch-row-desc">Allow sending measured shot summaries to your configured AI provider</div></div>
                <div class="switch ${pr.allow_cloud_ai ? "on" : ""}" data-act="privacy-toggle" data-field="allow_cloud_ai"></div>
              </div>
            </div>

            <div class="grid-2" style="gap:10px">
              <div class="field">
                <label>Hardware Acceleration</label>
                <select class="select" data-perf-cfg="hw_accel">
                  <option value="auto" ${pf.hw_accel === "auto" ? "selected" : ""}>Auto GPU (NVENC/QSV) + CPU Fallback</option>
                  <option value="cpu" ${pf.hw_accel === "cpu" ? "selected" : ""}>CPU Software Only (x264/x265)</option>
                </select>
              </div>
              <div class="field">
                <label><span>Analysis Sample Rate</span><span class="mono">${pf.sample_fps || 1.5} fps</span></label>
                <input type="range" min="0.5" max="4.0" step="0.5" value="${pf.sample_fps || 1.5}" data-perf-cfg="sample_fps" />
              </div>
            </div>
            <div class="switch-row" style="margin-top:6px">
              <div style="min-width:0">
                <div class="switch-row-title">Offline Speech-to-Text Package (Local Auto-Captions)</div>
                <div class="switch-row-desc">${S.speechModel && S.speechModel.ready ? "Installed locally — automatic word-timed captions enabled for local PC videos (no API key)" : S.speechModel && S.speechModel.doing ? `Downloading: ${S.speechModel.percent}% (${S.speechModel.downloaded_mb} / ${S.speechModel.total_mb} MB)` : "Optional ~480 MB one-time offline model for local video files (YouTube links don't need this)"}</div>
              </div>
              ${S.speechModel && S.speechModel.ready
                ? `<span class="badge score-high">Installed</span>`
                : `<button class="btn btn-primary btn-sm" data-act="open-speech-modal">${S.speechModel && S.speechModel.doing ? `${S.speechModel.percent}%` : "Download"}</button>`}
            </div>
            <div class="switch-row" style="margin-top:6px">
              <div style="min-width:0">
                <div class="switch-row-title">Local Data Directory</div>
                <div class="switch-row-desc mono" style="overflow:hidden;text-overflow:ellipsis">${esc(about.data_dir || "")}</div>
              </div>
              ${window.agentvidDesktop && about.data_dir ? `<button class="btn btn-sm" data-act="open-path" data-path="${esc(about.data_dir)}">Open</button>` : ""}
            </div>
          </div>
        </div>

        <!-- ABOUT AGENTVID -->
        <div class="panel" style="background:var(--surface);border-color:var(--border-strong)">
          <div class="row-between wrap" style="gap:18px;align-items:center;padding-bottom:16px;border-bottom:1px solid var(--border);margin-bottom:16px">
            <div class="row" style="gap:16px;align-items:center">
              <img src="/brand/favicon.svg" alt="AgentVid" style="width:62px;height:62px;border-radius:15px" />
              <div>
                <div style="font-size:21px;font-weight:750;letter-spacing:0.12em">AGENTVID</div>
                <div style="font-size:13px;color:var(--cyan);font-weight:500">AI Video Creation &amp; Editing Studio</div>
                <div style="margin-top:6px;font-size:12px;color:var(--text-1)">
                  Created by <strong>i.sayak007</strong> · Powered by <strong>Creative Creature (WE.ARECC)</strong>
                </div>
              </div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px">
              <img class="cc-logo-panel" src="/brand/creative-creature-logo.png" alt="Creative Creature" />
              <div class="row">
                <span class="badge score-strong">Version ${esc(about.version || "1.0.0")}</span>
                <span class="badge">${esc(about.build || "Windows Standalone Studio")}</span>
              </div>
            </div>
          </div>

          <div class="grid-4" style="margin-bottom:16px">
            <div class="stat-card" style="padding:11px 13px">
              <div class="stat-label">Render Engine</div>
              <div style="font-weight:650;font-size:13px;margin-top:4px;color:${about.ffmpeg_ready ? "var(--emerald)" : "var(--rose)"}">${about.ffmpeg_ready ? "FFmpeg Ready" : "FFmpeg Missing"}</div>
              <div class="stat-sub">H.264 / H.265 + Hardware Accel</div>
            </div>
            <div class="stat-card" style="padding:11px 13px">
              <div class="stat-label">Vision Face AI</div>
              <div style="font-weight:650;font-size:13px;margin-top:4px;color:var(--cyan)">Local Neural ONNX</div>
              <div class="stat-sub">5-Point Landmark Tracking</div>
            </div>
            <div class="stat-card" style="padding:11px 13px">
              <div class="stat-label">Pulse Virality</div>
              <div style="font-weight:650;font-size:13px;margin-top:4px;color:var(--violet)">15-Factor Model</div>
              <div class="stat-sub">Transparent Weighted Analytics</div>
            </div>
            <div class="stat-card" style="padding:11px 13px">
              <div class="stat-label">Runtime Environment</div>
              <div style="font-weight:650;font-size:13px;margin-top:4px">Desktop Standalone</div>
              <div class="stat-sub">${esc(about.os || "Windows")} · Local First</div>
            </div>
          </div>

          <div class="row-between wrap" style="gap:10px">
            <div class="row wrap" style="gap:8px">
              <button class="btn btn-primary btn-sm" data-act="open-external" data-url="https://isayak007.vercel.app/">${svg("external", 12)} Creator Website (isayak007.vercel.app)</button>
              <button class="btn btn-sm" data-act="open-external" data-url="https://www.instagram.com/we.arecc/">${svg("external", 12)} Creative Creature Instagram (@we.arecc)</button>
            </div>
            <div class="muted" style="font-size:11px">© 2026 Creative Creature (WE.ARECC) · i.sayak007 · MIT License</div>
          </div>
        </div>
      </div>
    `;
  }

  return {
    renderSubmitVideo,
    renderHome,
    renderProjects,
    renderEditor,
    renderAnalysis,
    renderShotLibrary,
    renderVirality,
    renderCaptions,
    renderExport,
    renderSettings,
  };
})();
