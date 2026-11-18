"""Comprehensive End-to-End Test Suite for AgentVid Studio."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def env_data(tmp_path_factory):
    d = tmp_path_factory.mktemp("agentvid_test_data")
    os.environ["AGENTVID_DATA"] = str(d)
    os.environ["PEAKCUT_DATA"] = str(d)
    os.environ["PEAKCUT_ACCOUNTS"] = "0"
    os.environ["PEAKCUT_UPDATE_CHECK"] = "0"
    os.environ["PEAKCUT_FETCH_MODEL"] = "0"
    return d


@pytest.fixture(scope="module")
def client(env_data):
    from studio import db, server
    db.init()
    with TestClient(server.app, base_url="http://127.0.0.1:8765") as c:
        yield c


@pytest.fixture(scope="module")
def sample_video(tmp_path_factory) -> Path:
    """Create a real multi-scene 1280x720 MP4 with distinct visual scenes and audio + silence."""
    td = tmp_path_factory.mktemp("media_src")
    raw_vid = td / "raw.avi"
    out_mp4 = td / "studio_sample.mp4"

    w, h, fps = 640, 360, 15
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(raw_vid), fourcc, fps, (w, h))

    # 3 distinct visual scenes (3 seconds each = 9 seconds total) so scene detection finds real cuts
    for frame_i in range(fps * 9):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        if frame_i < fps * 3:
            # Scene 1: Bright warm orange/cyan moving geometric blocks
            img[:, :] = (30, 90, 210)
            cx = int(120 + (frame_i * 6) % 400)
            cv2.rectangle(img, (cx, 60), (cx + 120, 280), (240, 210, 40), -1)
            cv2.circle(img, (320, 180), 70, (255, 255, 255), 5)
        elif frame_i < fps * 6:
            # Scene 2: High-contrast teal/green scene with moving texture
            img[:, :] = (160, 190, 40)
            cy = int(40 + ((frame_i - fps * 3) * 5) % 200)
            cv2.circle(img, (320, cy + 60), 85, (20, 40, 180), -1)
            cv2.line(img, (0, cy), (w, h - cy), (255, 255, 255), 8)
        else:
            # Scene 3: Deep indigo/magenta studio scene
            img[:, :] = (150, 25, 110)
            cv2.ellipse(img, (320, 180), (140, 90), frame_i * 3, 0, 360, (250, 180, 70), -1)
        writer.write(img)
    writer.release()

    # Mux with real audio: 0-3s 440Hz tone, 3-6s silence, 6-9s 660Hz tone
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(raw_vid),
        "-f", "lavfi", "-i",
        "aevalsrc='if(lt(t,3),0.35*sin(2*PI*440*t),if(lt(t,6),0,0.4*sin(2*PI*660*t)))':s=44100:d=9",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(out_mp4),
    ]
    subprocess.run(cmd, check=True)
    assert out_mp4.is_file() and out_mp4.stat().st_size > 10_000
    return out_mp4


def test_branding_and_health(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True

    about = client.get("/api/v2/about").json()
    assert about["product_name"] == "AgentVid"
    assert about["agency"] == "Creative Creature"
    assert about["agency_identity"] == "WE.ARECC"
    assert about["creator"] == "i.sayak007"
    assert about["creator_website"] == "https://isayak007.vercel.app/"
    assert about["agency_instagram"] == "https://www.instagram.com/we.arecc/"
    assert about["ffmpeg_ready"] is True

    # Ensure UI shell serves cleanly without PeakCut branding
    page = client.get("/app")
    assert page.status_code == 200
    assert "AgentVid" in page.text
    assert "PeakCut" not in page.text


def test_auto_manual_toggle_preserves_individual_switches(client):
    # Set custom switch states
    r = client.put("/api/v2/settings", json={
        "auto_mode": True,
        "automation": {
            "broll_suggestions": False,
            "export_preparation": True,
            "face_detection": True,
        },
    })
    assert r.status_code == 200
    st = r.json()["settings"]
    assert st["auto_mode"] is True
    assert st["automation"]["broll_suggestions"] is False
    assert st["automation"]["export_preparation"] is True
    assert len(st["automation"]) == 14

    # Toggle auto_mode OFF -> saved individual switches must remain untouched!
    r2 = client.put("/api/v2/settings", json={"auto_mode": False})
    assert r2.status_code == 200
    st2 = r2.json()["settings"]
    assert st2["auto_mode"] is False
    assert st2["automation"]["broll_suggestions"] is False
    assert st2["automation"]["export_preparation"] is True
    assert st2["automation"]["face_detection"] is True


def test_project_crud_autosave_recovery_and_security(client):
    # Create
    c = client.post("/api/v2/projects", json={"name": "Creative Launch", "description": "Studio test"})
    assert c.status_code == 200
    pid = c.json()["project"]["id"]

    # Rename
    rn = client.put(f"/api/v2/projects/{pid}/rename", json={"name": "Creative Launch Final"})
    assert rn.status_code == 200
    assert rn.json()["project"]["name"] == "Creative Launch Final"

    # Autosave & Recovery
    asv = client.post(f"/api/v2/projects/{pid}/autosave", json={"description": "Recovered description"})
    assert asv.status_code == 200 and asv.json()["ok"] is True
    got = client.get(f"/api/v2/projects/{pid}").json()["project"]
    assert got["has_recovery"] is True
    rec = client.post(f"/api/v2/projects/{pid}/recover", json={"accept": True}).json()["project"]
    assert rec["description"] == "Recovered description"
    assert rec["has_recovery"] is False

    # Duplicate
    dup = client.post(f"/api/v2/projects/{pid}/duplicate", json={"name": "Launch Copy"})
    assert dup.status_code == 200
    dup_id = dup.json()["project"]["id"]
    assert dup_id != pid

    # Security: path traversal & invalid project id blocked
    assert client.get("/api/v2/projects/../../etc/passwd").status_code in (400, 404)
    assert client.get(f"/api/v2/projects/{pid}/media/..%2Fproject.json").status_code in (400, 403, 404)
    assert client.post(f"/api/v2/projects/{pid}/media/import-local", json={"path": "C:/Windows/notepad.exe"}).status_code == 400

    # Delete duplicate
    assert client.delete(f"/api/v2/projects/{dup_id}").status_code == 200
    assert client.delete(f"/api/v2/projects/{pid}").status_code == 200


def test_full_end_to_end_pipeline_editing_captions_and_export(client, sample_video):
    # 1. Put in MANUAL mode first and import video -> should NOT auto-run shots
    client.put("/api/v2/settings", json={"auto_mode": False})
    pid = client.post("/api/v2/projects", json={"name": "E2E Studio Film"}).json()["project"]["id"]

    imp = client.post(
        f"/api/v2/projects/{pid}/media/import-local",
        json={"path": str(sample_video), "kind": "video", "trigger_auto": True},
    )
    assert imp.status_code == 200
    proj = imp.json()["project"]
    assert len(proj["media"]) == 1
    assert proj["media"][0]["width"] == 640
    assert proj["media"][0]["height"] == 360
    assert len(proj["shots"]) == 0  # MANUAL mode respected!

    # 2. Switch to AUTO mode and run full pipeline synchronously
    client.put("/api/v2/settings", json={"auto_mode": True})
    run = client.post(
        f"/api/v2/projects/{pid}/automation/run",
        json={"trigger": "auto", "sync": True},
    )
    assert run.status_code == 200
    assert run.json()["automation"]["state"] == "done"

    proj = run.json()["project"]
    shots = proj["shots"]
    assert len(shots) >= 1  # Short 9s source fits into 1 Reel (longer podcasts extract N scattered Peak Reels)
    assert len(proj["analysis"]["silence_segments"]) >= 1  # Real silence detection found the 3-6s silent segment!

    # Verify thumbnails exist on disk and are servable
    for sh in shots:
        assert sh["thumbnail_url"]
        tr = client.get(sh["thumbnail_url"])
        assert tr.status_code == 200 and len(tr.content) > 500
        # Verify all 15 virality dimensions calculated
        dims = sh["virality"]["dimensions"]
        assert len(dims) == 15
        assert 0 <= sh["virality"]["score"] <= 100

    assert proj["virality"]["overall_score"] > 0
    assert proj["virality"]["highest_shot_id"] is not None
    assert proj["face_tracking"]["status"] == "done"
    assert "9:16" in proj["face_tracking"]["reframing_suggestions"]

    # 3. Virality query sorting & filtering
    vq = client.get(f"/api/v2/projects/{pid}/virality/shots?sort_by=hook_strength&min_score=0&max_score=100")
    assert vq.status_code == 200
    assert len(vq.json()["shots"]) == len(shots)

    # 4. Non-destructive timeline editing: trim, zoom, speed, transition, text overlay, split, merge, reorder
    s0 = shots[0]
    ed = client.put(f"/api/v2/projects/{pid}/shots/{s0['id']}", json={
        "speed": 1.2,
        "zoom": 1.15,
        "pan_x": 0.45,
        "pan_y": 0.5,
        "transition": "fade",
        "text_overlay": "AGENTVID STUDIO",
    })
    assert ed.status_code == 200

    # Split first shot
    mid = round((s0["trim_start"] + s0["trim_end"]) / 2.0, 2)
    sp = client.post(f"/api/v2/projects/{pid}/shots/{s0['id']}/split", json={"split_at": mid})
    assert sp.status_code == 200
    shots_after_split = sp.json()["project"]["shots"]
    assert len(shots_after_split) == len(shots) + 1

    # Merge the two halves back
    mg = client.post(f"/api/v2/projects/{pid}/shots/merge", json={
        "shot_a": shots_after_split[0]["id"],
        "shot_b": shots_after_split[1]["id"],
    })
    assert mg.status_code == 200
    assert len(mg.json()["project"]["shots"]) == len(shots)

    # 5. Captions & Motion Graphics (add cues + configure Liquid Glass + Word Reveal)
    tl = client.put(f"/api/v2/projects/{pid}/timeline", json={
        "aspect": "9:16",
        "caption_config": {
            "enabled": True,
            "style": "liquid_glass",
            "animation": "word_reveal",
            "font_size": 64,
            "color": "#FFFFFF",
            "highlight_color": "#38BDF8",
        },
        "captions": [
            {"id": "c1", "start": 0.2, "end": 2.4, "text": "AgentVid Motion Captions", "words": [
                {"w": "AgentVid", "s": 0.2, "e": 0.9},
                {"w": "Motion", "s": 0.9, "e": 1.6},
                {"w": "Captions", "s": 1.6, "e": 2.4},
            ]},
        ],
    })
    assert tl.status_code == 200

    # 6. AI Assistant (grounded local mode without fabricating transcripts)
    ai_res = client.post(f"/api/v2/projects/{pid}/assistant", json={"action": "strongest_moments", "prompt": "Find best clips"})
    assert ai_res.status_code == 200
    assert "Shot" in ai_res.json()["reply"]
    assert ai_res.json()["mode"] == "local_analytics"

    # 7. Real FFmpeg Export (9:16 720p H.264) and verify exported MP4 via ffprobe!
    exp = client.post(f"/api/v2/projects/{pid}/export", json={
        "mode": "full",
        "codec": "h264",
        "resolution": "720p",
        "aspect": "9:16",
        "fps": 24,
        "quality": "draft",
        "sync": True,
    })
    assert exp.status_code == 200
    ej = exp.json()["export"]
    assert ej["status"] == "done", f"Export failed: {ej.get('error')} | Logs: {ej.get('logs')}"
    out_file = Path(ej["internal_path"])
    assert out_file.is_file() and out_file.stat().st_size > 10_000

    from studio import projects as av_projects
    probed = av_projects.probe_media_file(out_file)
    assert probed["has_video"] is True
    assert probed["has_audio"] is True
    assert probed["width"] == 720
    assert probed["height"] == 1280
    assert probed["duration"] > 3.0

    # Face tracking reset works cleanly
    rst = client.post(f"/api/v2/projects/{pid}/faces/reset")
    assert rst.status_code == 200
    assert rst.json()["project"]["face_tracking"]["status"] == "idle"


def test_creative_creature_logo_and_submit_link_validation(client):
    logo = client.get("/brand/creative-creature-logo.png")
    assert logo.status_code == 200 and len(logo.content) > 2000

    views_js = client.get("/assets/agentvid-views.js")
    assert views_js.status_code == 200
    assert "creative-creature-logo.png" in views_js.text
    assert "Submit a podcast or video link" in views_js.text
    assert "toggle-editor-captions" in views_js.text
    assert "peakcut" not in views_js.text.lower()

    # Ingest validation rejects unsupported/arbitrary URLs
    bad = client.post("/api/v2/ingest/preview", json={"url": "https://example.com/not-a-video"})
    assert bad.status_code == 400
    empty = client.post("/api/v2/ingest/url", json={"url": ""})
    assert empty.status_code == 400

    # Offline speech model status & download popup wiring
    sm = client.get("/api/v2/speech-model/status")
    assert sm.status_code == 200
    sm_data = sm.json()["speech_model"]
    assert sm_data["library_installed"] is True
    assert "ready" in sm_data and "percent" in sm_data
    app_js = client.get("/assets/agentvid-app.js").text
    assert "openSpeechModelModal" in app_js
    assert "Offline Auto-Captions Package" in app_js
    assert "Now you can totally use this software for free." in app_js
    assert "/api/newsletter" in app_js


def test_first_launch_onboarding_persistence_and_newsletter_proxy(client):
    # Starts as not completed (first launch only!)
    st = client.get("/api/v2/settings").json()["settings"]
    assert st["onboarding"]["completed"] is False

    # Invalid email rejected locally with 400 + exact error JSON
    bad1 = client.post("/api/newsletter", json={"email": ""})
    assert bad1.status_code == 400
    assert bad1.json() == {"error": "Valid email is required"}

    bad2 = client.post("/api/newsletter", json={"email": "not-an-email"})
    assert bad2.status_code == 400
    assert bad2.json() == {"error": "Valid email is required"}

    # Valid email forwarded to live upstream https://isayak007.vercel.app/api/newsletter
    good = client.post("/api/newsletter", json={"email": "agentvid.qa.test@example.com"})
    assert good.status_code == 200, f"Unexpected status {good.status_code}: {good.text}"
    assert good.json().get("success") is True

    # Completing onboarding persists permanently so subsequent launches never show it again
    done = client.put("/api/v2/settings", json={"onboarding": {"completed": True}})
    assert done.status_code == 200
    assert done.json()["settings"]["onboarding"]["completed"] is True
    st_after = client.get("/api/v2/settings").json()["settings"]
    assert st_after["onboarding"]["completed"] is True
    assert st_after["onboarding"]["newsletter_subscribed"] is True


def test_liquid_metal_shader_export_and_custom_font_upload(client, sample_video):
    # 1. Verify all 19 presets & bundled fonts are registered
    st = client.get("/api/v2/settings").json()
    style_ids = {s["id"] for s in st["caption_styles"]}
    for expected in ("liquid_silver", "molten_gold", "glossy_pink", "hyper_gradient", "cobalt_pulse", "solar_plasma", "swiss_minimal", "whisper_mono"):
        assert expected in style_ids
    assert len(st["fonts"]) >= 3

    # 2. Upload a real TTF font as a custom font and reject a corrupt file
    bad_f = client.post("/api/v2/fonts/upload", files={"file": ("bad.ttf", b"not a font", "font/ttf")})
    assert bad_f.status_code == 400

    sample_ttf = Path(r"F:/ai sites data/agent vid/studio/fonts/ArchivoBlack-Regular.ttf")
    up = client.post("/api/v2/fonts/upload", files={"file": ("MyLiquidDisplay.ttf", sample_ttf.read_bytes(), "font/ttf")})
    assert up.status_code == 200
    custom_font = up.json()["font"]
    assert custom_font["custom"] is True
    assert client.get(custom_font["url"]).status_code == 200

    # 3. Real FFmpeg export with Liquid Metal Silver shader captions + custom uploaded font
    pid = client.post("/api/v2/projects", json={"name": "Liquid Metal QA"}).json()["project"]["id"]
    client.put("/api/v2/settings", json={"auto_mode": False})
    client.post(f"/api/v2/projects/{pid}/media/import-local", json={"path": str(sample_video), "kind": "video", "trigger_auto": False})
    client.post(f"/api/v2/projects/{pid}/automation/run", json={"trigger": "manual", "tasks": ["scene_detection"], "sync": True})
    client.put(f"/api/v2/projects/{pid}/timeline", json={
        "aspect": "9:16",
        "caption_config": {
            "enabled": True,
            "style": "liquid_silver",
            "animation": "pop_in",
            "font": custom_font["family"],
            "font_size": 76,
            "uppercase": True,
        },
        "captions": [{"id": "lm1", "start": 0.2, "end": 4.0, "text": "LIQUID METAL", "words": []}],
    })
    exp = client.post(f"/api/v2/projects/{pid}/export", json={
        "mode": "full", "codec": "h264", "resolution": "720p", "aspect": "9:16", "fps": 24, "quality": "draft", "sync": True,
    })
    assert exp.status_code == 200
    ej = exp.json()["export"]
    assert ej["status"] == "done", ej
    out_mp4 = Path(ej["internal_path"])
    assert out_mp4.is_file() and out_mp4.stat().st_size > 15_000

    # Save a frame check so we can visually verify Liquid Metal Silver shader rendering
    check_jpg = Path(r"F:/ai sites data/agent vid/qa_reels_output/liquid_metal_frame_check.jpg")
    check_jpg.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.5", "-i", str(out_mp4), "-frames:v", "1", "-q:v", "3", str(check_jpg)], check=True)

    # 4. Delete custom font cleanly
    assert client.delete(f"/api/v2/fonts/{custom_font['filename']}").status_code == 200


def test_podcast_peak_reel_selection_and_editor_caption_controls(client, sample_video, monkeypatch):
    from studio import ai, brain, projects as av_projects, reel_selector, virality

    # 1. Settings persistence for Reels count, fixed vs AI timing, and Auto-Captions default
    r1 = client.put("/api/v2/settings", json={
        "reels": {"count": 10, "duration_mode": "fixed", "target_duration": 30, "aspect": "9:16", "auto_captions": True}
    })
    assert r1.status_code == 200
    rc = r1.json()["settings"]["reels"]
    assert rc["count"] == 10
    assert rc["duration_mode"] == "fixed"
    assert rc["target_duration"] == 30
    assert rc["auto_captions"] is True

    r2 = client.put("/api/v2/settings", json={"reels": {"duration_mode": "auto_ai"}})
    assert r2.status_code == 200
    assert r2.json()["settings"]["reels"]["duration_mode"] == "auto_ai"

    # 2. Non-sequential peak selection across a simulated 1-hour (3600s) podcast
    duration = 3600.0
    db = np.full(int(duration), -42.0, dtype=np.float32)
    peak_centers = [420, 1170, 1875, 2640, 3200]  # 7:00, 19:30, 31:15, 44:00, 53:20
    speech_segs = []
    for c in peak_centers:
        db[c - 15:c + 20] = -10.0
        speech_segs.append({"start": float(c - 15), "end": float(c + 20)})
    local_picks = reel_selector._local_peak_windows(
        duration=duration,
        db=db,
        audio_info={"speech_segments": speech_segs, "silence_segments": [], "transcript_words": []},
        count=5,
        target_len=30.0,
        min_len=18.0,
        max_len=58.0,
        duration_mode="fixed",
    )
    assert len(local_picks) == 5
    # Verify picks are non-overlapping and hit the scattered peak zones across the hour (NOT sequential 0..150s!)
    assert local_picks[0]["start"] > 300.0
    assert local_picks[-1]["start"] > 3000.0
    for i in range(1, len(local_picks)):
        assert local_picks[i]["start"] >= local_picks[i - 1]["end"]

    # 3. AI Peak Finder path (mocked AI provider picking variable Shorts/Reels lengths)
    pid = client.post("/api/v2/projects", json={"name": "1-Hour Podcast QA"}).json()["project"]["id"]
    client.put("/api/v2/settings", json={"auto_mode": False})
    imp = client.post(
        f"/api/v2/projects/{pid}/media/import-local",
        json={"path": str(sample_video), "kind": "video", "trigger_auto": False},
    )
    proj = imp.json()["project"]
    media_meta, vpath = av_projects.get_active_media(proj)

    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(ai, "label", lambda: "Gemini")
    monkeypatch.setattr(
        brain,
        "find_clips",
        lambda **kwargs: (
            [
                {"start": 0.5, "end": 3.5, "score": 91, "category": "take", "hook": "BOLD TAKE", "title": "Peak Moment One", "reason": "High-impact podcast hook."},
                {"start": 5.5, "end": 8.5, "score": 87, "category": "story", "hook": "WILD STORY", "title": "Peak Moment Two", "reason": "Memorable closing payoff."},
            ],
            {"model": "gemini-2.5-flash", "tokens": 1240, "note": ""},
        ),
    )

    fake_words = [{"w": f"word{i}", "s": round(i * 0.4, 2), "e": round(i * 0.4 + 0.35, 2)} for i in range(20)]
    seg = reel_selector.build_peak_reels(
        pid=pid,
        video_path=vpath,
        media_meta=media_meta,
        audio_info={"rms_timeline": [], "silence_segments": [], "speech_segments": [], "transcript_words": fake_words, "audio_clarity": 80},
        reel_settings={"count": 2, "duration_mode": "auto_ai", "min_duration": 18, "max_duration": 58},
        allow_ai=True,
    )
    assert seg["selection_mode"] == "ai_peak_detection"
    assert seg["ai_model"] == "gemini-2.5-flash"
    assert len(seg["shots"]) == 2
    assert seg["shots"][0]["cut_kind"] == "ai_peak_reel"
    assert seg["shots"][0]["hook"] == "BOLD TAKE"
    assert seg["shots"][1]["start"] == 5.5  # Skipped the silent 3.5-5.5s middle!

    # Verify virality preserves AI reason & blends AI score
    vres = virality.score_project_shots(seg["shots"], float(media_meta["duration"]))
    assert "High-impact podcast hook." in vres["shots"][0]["virality"]["recommendation"]
    assert vres["shots"][0]["virality"]["source"] == "ai_peak_plus_local_model"

    # Save those 2 Peak Reels onto the project and test Studio Editor Auto-Captions toggle + drag Y position + batch export!
    proj["shots"] = vres["shots"]
    av_projects.save_project(pid, proj)

    t_off = client.put(f"/api/v2/projects/{pid}/timeline", json={"caption_config": {"enabled": False, "y_offset": 42, "position": "center"}})
    assert t_off.status_code == 200
    cc = t_off.json()["project"]["timeline"]["caption_config"]
    assert cc["enabled"] is False
    assert cc["y_offset"] == 42
    assert cc["position"] == "center"

    pack = client.post(f"/api/v2/projects/{pid}/export/reels", json={
        "use_timeline_reels": True,
        "count": 2,
        "resolution": "720p",
        "fps": 24,
        "quality": "draft",
        "sync": True,
    })
    assert pack.status_code == 200
    pj = pack.json()["export"]
    assert pj["status"] == "done", pj
    assert pj["captions_enabled"] is False
    assert len(pj["reels"]) == 2
    for r in pj["reels"]:
        assert Path(r["internal_path"]).is_file()


def test_dynamic_ai_multilanguage_captions_and_xy_size_controls(client, sample_video, monkeypatch):
    from studio import ai, ai_transcribe, editor_engine

    # 1. Regression test for frozen caption bug ("spee" at 2.0s + "for" at 28.0s MUST NEVER freeze for 26s!)
    cues = ai_transcribe.words_to_cues([
        {"w": "spee", "s": 2.0, "e": 2.3},
        {"w": "for", "s": 28.0, "e": 28.4},
    ])
    assert len(cues) == 2
    assert cues[0]["end"] - cues[0]["start"] < 1.5
    assert cues[1]["start"] == 28.0 and cues[1]["end"] - cues[1]["start"] < 1.5

    # 2. Settings caption_defaults (language, x_offset horizontal, y_offset vertical, font_size)
    st = client.get("/api/v2/settings").json()
    lang_ids = {x["id"] for x in st["caption_languages"]}
    assert {"auto", "en", "hi", "hi-Latn", "bn", "bn-Latn", "en-translate"}.issubset(lang_ids)

    upd = client.put("/api/v2/settings", json={
        "caption_defaults": {"language": "hi-Latn", "x_offset": 30, "y_offset": 68, "font_size": 78}
    })
    assert upd.status_code == 200
    cd = upd.json()["settings"]["caption_defaults"]
    assert cd["language"] == "hi-Latn"
    assert cd["x_offset"] == 30
    assert cd["y_offset"] == 68
    assert cd["font_size"] == 78

    # 3. Verify ASS generator honors horizontal x_offset (30% of 1080 = 324) + vertical y_offset (68% of 1920 = 1306)
    ass = editor_engine.build_motion_ass(
        captions=[{"start": 0.5, "end": 2.0, "text": "Kya baat hai", "words": []}],
        text_overlays=[],
        caption_cfg={"enabled": True, "style": "minimal", "animation": "pop_in", "x_offset": 30, "y_offset": 68, "font_size": 78},
        out_w=1080,
        out_h=1920,
    )
    assert r"\pos(324,1306)" in ass

    # 4. Multi-language AI Audio Caption Generation endpoint (/captions/generate) with mocked Gemini audio
    pid = client.post("/api/v2/projects", json={"name": "Hinglish Captions QA"}).json()["project"]["id"]
    client.put("/api/v2/settings", json={"auto_mode": False})
    client.post(f"/api/v2/projects/{pid}/media/import-local", json={"path": str(sample_video), "kind": "video", "trigger_auto": False})
    client.post(f"/api/v2/projects/{pid}/automation/run", json={"trigger": "manual", "tasks": ["scene_detection"], "sync": True})

    monkeypatch.setattr(ai, "ready", lambda: True)
    monkeypatch.setattr(ai, "provider", lambda: "gemini")
    monkeypatch.setattr(ai, "label", lambda: "Gemini")
    monkeypatch.setattr(
        ai_transcribe,
        "_transcribe_chunk_gemini",
        lambda mp3_path, seg_dur, language: (
            [
                {"start": 0.4, "end": 1.9, "text": "Dekho ye kamaal"},
                {"start": 2.1, "end": 3.8, "text": "bilkul voice ke saath"},
                {"start": 6.2, "end": 8.0, "text": "captions badal rahe hain"},
            ],
            "gemini-2.5-flash",
        ),
    )

    gen = client.post(f"/api/v2/projects/{pid}/captions/generate", json={"language": "hi-Latn", "only_shots": True})
    assert gen.status_code == 200, gen.text
    gdata = gen.json()
    assert gdata["cues_count"] >= 3
    assert "ai_audio" in gdata["source"]
    proj = gdata["project"]
    assert proj["timeline"]["caption_config"]["language"] == "hi-Latn"
    assert proj["timeline"]["caption_config"]["x_offset"] == 30
    assert proj["timeline"]["caption_config"]["font_size"] == 78
    assert any("Dekho" in c["text"] for c in proj["timeline"]["captions"])
    assert any("badal rahe" in c["text"] for c in proj["timeline"]["captions"])
    assert "Dekho" in (proj["shots"][0].get("transcript") or "")





