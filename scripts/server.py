"""
claudio.fm 本地伺服器
FastAPI + WebSocket，讓瀏覽器介面驅動完整 DJ 流程

啟動：
  cd scripts
  python -X utf8 server.py

開啟瀏覽器：http://localhost:8000
"""

import os
import re
import sys
import json
import time
import asyncio
import pathlib
import importlib.util
from collections import deque
from datetime import datetime

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).parent.parent / ".env")

# ── 路徑設定 ────────────────────────────────────────────────
SCRIPTS_DIR   = pathlib.Path(__file__).parent
AUDIO_DIR     = SCRIPTS_DIR.parent / "audio_output"
DJ_MUSIC_DIR  = SCRIPTS_DIR.parent / "DJ_music"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
DJ_MUSIC_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))

# ── Suno 限速：6 分鐘內最多 2 首 ─────────────────────────
_SUNO_TS: deque = deque()
_SUNO_WINDOW = 360  # 秒
_SUNO_EVERY  = 3    # 每 N 次廣播才觸發一次 Suno（避免搶完即等）
_broadcast_count = 0

def _can_run_suno() -> bool:
    now = time.time()
    while _SUNO_TS and now - _SUNO_TS[0] > _SUNO_WINDOW:
        _SUNO_TS.popleft()
    return len(_SUNO_TS) < 2

def _record_suno():
    _SUNO_TS.append(time.time())

def _suno_cooldown_remaining() -> int:
    if not _SUNO_TS:
        return 0
    return max(0, int(_SUNO_WINDOW - (time.time() - _SUNO_TS[0])))


# ── 音樂關鍵詞庫（依照 music規則.md） ───────────────────────
_NO = "no drums, no percussion, no strings, no orchestra, no bass, piano only, no beats"

_KW = {
    "A1": f"warm felt piano, intimate, sentimental, minimalism, very slow tempo, soft forest ambiance, relaxation, peaceful piano, gentle piano melody, soft piano, {_NO}",
    "A2": f"calm piano, soft flute melody, peaceful, focus, study ambiance, soft pads, concentration, {_NO}",
    "A3": f"calm piano, encouraging piano, peaceful piano, focus, confidence, gentle motivation, study support, {_NO}",
    "A4": f"peaceful piano, gentle piano melody, warm ambient textures, night sounds, sleep, calm ambient, lullaby, {_NO}",
    "C1": f"gentle piano, soft starlight whispers, tender lullaby melody, sleep embrace harmony, dream dust sparkles, night guardian bells, peaceful slumber ambient, {_NO}",
    "D2": f"warm felt piano, intimate, sentimental, minimalism, very slow tempo, soft forest ambiance, relaxation, peaceful piano, gentle piano melody, soft piano, {_NO}",
    "D3": f"432Hz sleep frequency, peaceful piano, gentle piano melody, soft sound of forest, night sounds, sleep, calm ambient, {_NO}",
    "E1": f"36Hz, gentle piano forest melody, atmosphere of blue skies and white clouds, tranquility of the forest for healing, {_NO}",
}

def _select_music_keywords(emotion: dict, persona: str) -> str:
    """依時段人設與情緒選擇符合規則的音樂關鍵詞"""
    mood = emotion.get("overall_mood", "neutral")
    if persona == "I人的时光":          # 00:00-03:00
        return _KW["A4"] if mood in ("melancholic", "introspective") else _KW["C1"]
    if persona == "深夜吧檯":           # 21:00-00:00
        return _KW["A1"] if mood in ("melancholic", "introspective") else _KW["A2"]
    # 晚安下班了 18:00-21:00 或預設
    if mood in ("melancholic", "introspective"):
        return _KW["A1"]
    if mood == "energetic":
        return _KW["A3"]
    return _KW["D2"]

AI_DJ_DIR = SCRIPTS_DIR.parent / "AI DJ"

app = FastAPI(title="我是你的朋友 - AJ")
app.mount("/audio",    StaticFiles(directory=str(AUDIO_DIR)),    name="audio")
app.mount("/dj_music", StaticFiles(directory=str(DJ_MUSIC_DIR)), name="dj_music")

@app.on_event("startup")
async def on_startup():
    """啟動時預載入審查引擎，確保第一條訊息不卡頓"""
    get_moderator()
    print("\n✅  claudio.fm 已就緒 → http://localhost:8000\n")

# 啟動時載入審查引擎（單例）
_moderator = None
def get_moderator():
    global _moderator
    if _moderator is None:
        import importlib.util as _ilu
        _src = SCRIPTS_DIR / "chat-moderator.py"
        _spec = _ilu.spec_from_file_location("chat_moderator", str(_src))
        _mod = _ilu.module_from_spec(_spec)
        sys.modules["chat_moderator"] = _mod
        _spec.loader.exec_module(_mod)
        _moderator = _mod.ChatModerator()
        print(f"[Mod] 黑名單已載入，pattern 數：{len(_moderator.patterns)}")
    return _moderator


# ── 模組載入（連字符檔名）───────────────────────────────────
def _load(mod_name: str, filename: str):
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    src = SCRIPTS_DIR / filename
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── WebSocket 推送輔助 ──────────────────────────────────────
async def push(ws: WebSocket, event: str, data: dict):
    await ws.send_text(json.dumps({"event": event, "data": data}, ensure_ascii=False))


# ── 核心流程（在 executor 裡跑，不阻塞 event loop）──────────
def run_pipeline(messages: list) -> dict:
    """同步執行完整流程，回傳各步結果"""
    results = {}

    # Step 1：情緒分析
    m = _load("emotion_analyzer", "emotion-analyzer.py")
    analyzer = m.EmotionAnalyzer()
    results["emotion"] = analyzer.analyze_batch(messages)

    # Step 2：DJ 台詞
    m2 = _load("dj_script_generator", "dj-script-generator.py")
    gen = m2.DJScriptGenerator()
    results["dj"] = gen.generate_script(mood_analysis=results["emotion"])

    # Step 3：Suno 音樂
    m3 = _load("suno_client", "suno-client.py")
    client = m3.SunoClient()
    job = client.generate(
        prompt=_build_music_prompt(results["emotion"]),
        title=f"claudio.fm × {results['dj']['persona']}",
        make_instrumental=True
    )
    results["suno_job"] = job

    if job.get("task_id"):
        audio_url = client.wait_for_audio(job["task_id"], timeout=180)
        results["music_url"] = audio_url or ""
    else:
        results["music_url"] = ""

    # Step 4：ElevenLabs TTS
    m4 = _load("elevenlabs_tts", "elevenlabs-tts.py")
    tts = m4.ElevenLabsTTS()
    persona = results["dj"].get("persona", "midnight")
    period_map = {"晚安下班了": "evening", "深夜吧檯": "midnight", "I人的时光": "late_night"}
    period_key = period_map.get(persona, "midnight")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = str(AUDIO_DIR / f"claudio_{period_key}_{ts}.mp3")
    tts.speak(text=results["dj"]["script"], time_period=period_key, output_path=out_path)
    results["tts_file"] = pathlib.Path(out_path).name

    return results


def _build_music_prompt(emotion: dict) -> str:
    m = _load("music_generator", "music-generator.py")
    gen = m.MusicPromptGenerator()
    h = datetime.now().hour
    if 18 <= h < 21:
        period = "evening"
    elif 21 <= h < 24:
        period = "midnight"
    else:
        period = "late_night"
    result = gen.generate_prompt(
        mood=emotion.get("overall_mood", "neutral"),
        time_period=period,
        keywords=emotion.get("keywords", [])[:3]
    )
    return result["prompt"]


# ── 曲庫 API ────────────────────────────────────────────────
@app.get("/api/library")
async def get_library():
    """回傳所有 Suno 已生成的 MP3，供前端背景播放用。
    優先掃 DJ_music（新），再掃 audio_output 子資料夾（舊）。
    """
    tracks = []
    # DJ_music 目錄（所有檔案都是音樂）
    if DJ_MUSIC_DIR.exists():
        for mp3 in sorted(DJ_MUSIC_DIR.rglob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True):
            rel = mp3.relative_to(DJ_MUSIC_DIR).as_posix()
            tracks.append(f"/dj_music/{rel}")
    # audio_output 子資料夾（舊版相容，TTS 在根目錄故排除）
    for mp3 in sorted(AUDIO_DIR.rglob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True):
        if mp3.parent != AUDIO_DIR:
            rel = mp3.relative_to(AUDIO_DIR).as_posix()
            tracks.append(f"/audio/{rel}")
    return JSONResponse({"tracks": tracks[:80]})


# ── 審查 API ────────────────────────────────────────────────
class ModerateRequest(BaseModel):
    text: str

@app.post("/api/moderate")
async def moderate_message(req: ModerateRequest):
    moderator = get_moderator()
    result = await moderator.moderate(req.text)
    return JSONResponse(result)


# ── Suno 背景任務 ──────────────────────────────────────────
async def _suno_background(ws: WebSocket, loop, dj_result: dict, emotion: dict, forced_music: str = ""):
    """背景生成 Suno 音樂：限速 → 生成 → 下載存到 DJ_music → 推送"""
    song_name = dj_result.get("song_name", "")

    # chat_reaction 等模式沒有歌名 → 用 DeepSeek 自動補一個
    if not song_name:
        try:
            m_gen = _load("dj_script_generator", "dj-script-generator.py")
            gen   = m_gen.DJScriptGenerator()
            _emo  = emotion
            song_name = await loop.run_in_executor(None, lambda: gen.generate_song_name(_emo))
            print(f"[DJ] 自動歌名：{song_name}")
        except Exception as e:
            song_name = f"AJ {datetime.now().strftime('%H%M')}"
            print(f"[DJ] 歌名生成失敗，使用預設：{song_name}（{e}）")

    # 限速檢查
    if not _can_run_suno():
        remaining = _suno_cooldown_remaining()
        await push(ws, "step", {
            "step": 3, "status": "done", "music_url": "",
            "msg": f"Suno 冷卻中（剩 {remaining}s），跳過本次生成"
        })
        return

    _record_suno()

    try:
        m3 = _load("suno_client", "suno-client.py")
        client = m3.SunoClient()

        # 優先用控制台指定風格，否則依時段+情緒自動選
        if forced_music and forced_music in _KW:
            music_keywords = _KW[forced_music]
            print(f"[Suno] 使用指定風格：{forced_music}")
        else:
            music_keywords = _select_music_keywords(emotion, dj_result.get("persona", ""))
        title = song_name or f"claudio.fm {datetime.now().strftime('%H%M')}"

        def _gen():
            return client.generate(
                prompt=music_keywords,
                title=title,
                make_instrumental=True,
            )

        job = await loop.run_in_executor(None, _gen)
        task_id = job.get("task_id", "")

        display_name = f"「{song_name}」"
        await push(ws, "step", {
            "step": 3, "status": "waiting",
            "task_id": task_id,
            "song_name": song_name,
            "msg": f"{display_name} 生成中，約 1-3 分鐘…"
        })

        if task_id:
            music_url = await loop.run_in_executor(
                None, client.wait_for_audio, task_id, 180, 10
            ) or ""
        else:
            music_url = ""

        # 下載 MP3 到 DJ_music/YYYYMMDD/{歌名}.mp3
        local_url = ""
        if music_url:
            today    = datetime.now().strftime("%Y%m%d")
            song_dir = DJ_MUSIC_DIR / today
            song_dir.mkdir(parents=True, exist_ok=True)
            safe     = re.sub(r"[^\w\s-]", "", song_name or "untitled").strip().replace(" ", "_")
            # 避免同名衝突
            mp3_path = song_dir / f"{safe}.mp3"
            counter  = 2
            while mp3_path.exists():
                mp3_path = song_dir / f"{safe}_{counter}.mp3"
                counter += 1
            mp3_name = mp3_path.name
            try:
                await loop.run_in_executor(
                    None, lambda: client.download_audio(music_url, str(mp3_path))
                )
                local_url = f"/dj_music/{today}/{mp3_name}"
                print(f"[Suno] 已儲存：{mp3_path}")
            except Exception as dl_err:
                print(f"[Suno] 下載失敗，改用串流 URL：{dl_err}")

        serve_url = local_url or music_url
        await push(ws, "step", {
            "step": 3, "status": "done",
            "music_url": serve_url,
            "song_name": song_name
        })
        if serve_url:
            await push(ws, "music_ready", {
                "music_url": serve_url,
                "song_name": song_name
            })
    except Exception as e:
        try:
            await push(ws, "error", {"step": 3, "msg": str(e)})
        except Exception:
            pass


# ── WebSocket 端點 ──────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    loop = asyncio.get_event_loop()

    try:
        while True:
            raw = await ws.receive_text()
            payload = json.loads(raw)
            messages       = payload.get("messages", [])
            mode           = payload.get("mode", "chat_reaction")
            theme          = payload.get("theme", "")
            forced_persona = payload.get("forced_persona", "")
            forced_music   = payload.get("forced_music", "")
            suno_enabled   = payload.get("suno_enabled", True)
            script_history = payload.get("script_history", [])
            voice_id       = payload.get("voice_id", "")

            # song_premiere 若 Suno 關閉或冷卻中，降級為 motivation
            if mode == "song_premiere" and (not suno_enabled or not _can_run_suno()):
                remaining = _suno_cooldown_remaining()
                reason = "已關閉" if not suno_enabled else f"冷卻中（剩 {remaining}s）"
                print(f"[Rate] Suno {reason}，song_premiere → motivation")
                mode = "motivation"

            NEEDS_EMOTION = mode in ("chat_reaction", "song_premiere")
            global _broadcast_count
            _broadcast_count += 1
            NEEDS_SUNO = suno_enabled and (
                mode == "song_premiere" or
                _broadcast_count % _SUNO_EVERY == 0
            )

            if not messages and mode == "chat_reaction":
                await push(ws, "error", {"msg": "請至少輸入一條留言"})
                continue

            await push(ws, "start", {"count": len(messages), "mode": mode})

            emotion = {
                "overall_mood": "neutral", "dominant_emotion": "neutral",
                "keywords": [], "summary": ""
            }

            # Step 1: 情緒分析（部分模式略過）
            if NEEDS_EMOTION and messages:
                await push(ws, "step", {"step": 1, "status": "running", "label": "情緒分析"})
                try:
                    m = _load("emotion_analyzer", "emotion-analyzer.py")
                    analyzer = m.EmotionAnalyzer()
                    emotion = await loop.run_in_executor(None, analyzer.analyze_batch, messages)
                    await push(ws, "step", {
                        "step": 1, "status": "done",
                        "mood": emotion.get("overall_mood"),
                        "emotion": emotion.get("dominant_emotion"),
                        "keywords": emotion.get("keywords", []),
                        "summary": emotion.get("summary", "")
                    })
                except Exception as e:
                    await push(ws, "error", {"step": 1, "msg": str(e)})
            else:
                await push(ws, "step", {
                    "step": 1, "status": "done",
                    "mood": "—", "emotion": "—", "keywords": [], "summary": ""
                })

            # Step 2: DJ 台詞（依模式路由）
            await push(ws, "step", {"step": 2, "status": "running", "label": "DJ 台詞生成"})
            try:
                m2 = _load("dj_script_generator", "dj-script-generator.py")
                gen = m2.DJScriptGenerator()

                # song_premiere：先生成歌名，再讓 AJ 介紹
                song_name = ""
                if mode == "song_premiere":
                    _emo_snap = emotion
                    song_name = await loop.run_in_executor(
                        None, lambda: gen.generate_song_name(_emo_snap)
                    )
                    print(f"[DJ] 歌名：{song_name}")

                _mode, _msgs, _emo, _sname, _theme, _fp, _sh = mode, messages, emotion, song_name, theme, forced_persona, script_history
                dj = await loop.run_in_executor(
                    None,
                    lambda: gen.generate_by_mode(_mode, _msgs, _emo, _sname, _theme, _fp, _sh)
                )
                await push(ws, "step", {
                    "step": 2, "status": "done",
                    "script": dj["script"],
                    "persona": dj["persona"],
                    "time_range": dj["time_range"],
                    "mode": dj.get("mode", mode),
                    "song_name": dj.get("song_name", "")
                })
            except Exception as e:
                await push(ws, "error", {"step": 2, "msg": str(e)})
                continue

            # Step 4: TTS（立即執行，不等 Suno）
            await push(ws, "step", {"step": 4, "status": "running", "label": "AJ 開口說話"})
            try:
                m4   = _load("elevenlabs_tts", "elevenlabs-tts.py")
                _vid = m4.VOICE_ROSTER.get(voice_id) or voice_id or m4.DEFAULT_VOICE_ID
                tts  = m4.ElevenLabsTTS(voice_id=_vid)
                persona    = dj.get("persona", "midnight")
                period_map = {
                    "晚安下班了": "evening",
                    "深夜吧檯":   "midnight",
                    "I人的时光":  "late_night"
                }
                period_key = period_map.get(persona, "midnight")
                ts         = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path   = str(AUDIO_DIR / f"claudio_{period_key}_{ts}.mp3")
                _script    = dj["script"]

                def _tts():
                    tts.speak(text=_script, time_period=period_key, output_path=out_path)

                await loop.run_in_executor(None, _tts)
                filename = pathlib.Path(out_path).name
                await push(ws, "step", {
                    "step": 4, "status": "done",
                    "audio_url": f"/audio/{filename}",
                    "filename": filename
                })
            except Exception as e:
                await push(ws, "error", {"step": 4, "msg": str(e)})

            # TTS 完成，前端解除 loading
            await push(ws, "done", {"music_url": ""})

            # Step 3: Suno 背景任務（只有 chat_reaction / song_premiere 且未關閉）
            if NEEDS_SUNO:
                asyncio.create_task(_suno_background(ws, loop, dj, emotion, forced_music))

    except WebSocketDisconnect:
        pass


# ── 主頁：serve 現有 claudio-fm-index.html ─────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = AI_DJ_DIR / "claudio-fm-index.html"
    return HTMLResponse(
        content=html_file.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"}
    )


# ── 舊版內嵌 HTML（備用，不再使用）────────────────────────
HTML_PAGE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<title>claudio.fm — DJ 控制台</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=JetBrains+Mono:wght@300;400&family=Noto+Serif+TC:wght@300;400&display=swap" rel="stylesheet"/>
<style>
:root{
  --ink:#1a1714; --ink-2:#221d18; --paper:#e8e0d2;
  --paper-dim:#c9bfae; --paper-faint:#8a8170;
  --rule:#3a322a; --moss:oklch(0.62 0.04 145);
  --ember:oklch(0.68 0.09 55);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{
  background:var(--ink);color:var(--paper);min-height:100vh;
  font-family:"Cormorant Garamond","Noto Serif TC",serif;font-weight:400;
}
body{
  background:
    radial-gradient(ellipse 80% 60% at 70% 20%,oklch(0.22 0.02 60/.7),transparent 60%),
    radial-gradient(ellipse 60% 80% at 10% 90%,oklch(0.20 0.03 30/.6),transparent 70%),
    var(--ink);
}
body::before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:0.14;mix-blend-mode:overlay;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.4'/></svg>");
}
.mono{font-family:"JetBrains Mono",monospace;font-weight:300;letter-spacing:.03em}
.wrap{position:relative;z-index:1;max-width:960px;margin:0 auto;padding:40px 24px 80px}

/* header */
.header{border-bottom:1px solid var(--rule);padding-bottom:20px;margin-bottom:36px;display:flex;align-items:baseline;gap:16px}
.logo{font-size:1.7rem;font-style:italic;letter-spacing:.04em;color:var(--paper)}
.logo span{color:var(--ember)}
.tagline{font-size:.8rem;color:var(--paper-faint);font-family:"JetBrains Mono",monospace;letter-spacing:.08em}

/* chat input */
.section-label{font-size:.7rem;font-family:"JetBrains Mono",monospace;letter-spacing:.14em;color:var(--paper-faint);text-transform:uppercase;margin-bottom:10px}
.chat-area{width:100%;background:oklch(0.14 0.01 45/.8);border:1px solid var(--rule);color:var(--paper);font-family:"Noto Serif TC",serif;font-size:1rem;padding:14px 16px;resize:vertical;min-height:130px;border-radius:2px;outline:none;line-height:1.7}
.chat-area:focus{border-color:oklch(0.45 0.04 60)}
.chat-area::placeholder{color:var(--paper-faint)}
.hint{font-size:.75rem;color:var(--paper-faint);margin-top:7px;font-family:"JetBrains Mono",monospace}
.btn-row{display:flex;gap:12px;margin-top:16px;align-items:center}
.btn{
  background:oklch(0.62 0.07 45);color:var(--ink);border:none;
  padding:10px 28px;font-family:"Cormorant Garamond",serif;font-size:1rem;
  font-style:italic;cursor:pointer;border-radius:1px;letter-spacing:.04em;
  transition:opacity .2s;
}
.btn:hover{opacity:.85}
.btn:disabled{opacity:.4;cursor:not-allowed}
.status-badge{font-size:.75rem;font-family:"JetBrains Mono",monospace;color:var(--paper-faint)}

/* steps */
.steps{margin-top:36px;display:flex;flex-direction:column;gap:16px}
.step{
  border:1px solid var(--rule);border-radius:2px;padding:16px 20px;
  transition:border-color .3s,background .3s;
  background:oklch(0.13 0.01 45/.5);
}
.step.running{border-color:var(--ember);background:oklch(0.15 0.02 50/.6)}
.step.done{border-color:oklch(0.45 0.04 145/.8);background:oklch(0.13 0.02 145/.3)}
.step.error{border-color:oklch(0.5 0.1 20/.8)}
.step-header{display:flex;align-items:center;gap:12px}
.step-num{font-size:.7rem;font-family:"JetBrains Mono",monospace;color:var(--paper-faint);min-width:48px}
.step-label{font-size:.95rem;letter-spacing:.04em}
.step-icon{margin-left:auto;font-size:.8rem;font-family:"JetBrains Mono",monospace;color:var(--paper-faint)}
.step-body{margin-top:12px;padding-top:12px;border-top:1px solid var(--rule);display:none}
.step.done .step-body, .step.running .step-body, .step.waiting .step-body{display:block}

/* emotion tags */
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.tag{font-size:.7rem;font-family:"JetBrains Mono",monospace;padding:3px 8px;border:1px solid var(--rule);color:var(--paper-dim);border-radius:1px}

/* dj script */
.dj-script{
  font-size:1.15rem;font-style:italic;line-height:1.8;
  color:var(--paper);padding:12px 0;border-left:2px solid var(--ember);padding-left:16px;
  margin-top:8px;
}
.persona-badge{font-size:.7rem;font-family:"JetBrains Mono",monospace;color:var(--ember);margin-bottom:8px;letter-spacing:.08em}

/* music */
.music-url{font-size:.75rem;font-family:"JetBrains Mono",monospace;color:var(--moss);word-break:break-all;margin-top:8px}
.music-url a{color:var(--moss);text-decoration:none}
.music-url a:hover{text-decoration:underline}

/* audio player */
.player-wrap{margin-top:12px}
audio{width:100%;height:36px;filter:invert(1) sepia(1) hue-rotate(170deg) brightness(.8);border-radius:2px}

/* waiting pulse */
@keyframes pulse{0%,100%{opacity:.4}50%{opacity:1}}
.pulse{animation:pulse 1.4s ease-in-out infinite;display:inline-block;width:6px;height:6px;background:var(--ember);border-radius:50%;margin-right:8px;vertical-align:middle}

/* result card */
.result-card{
  margin-top:36px;padding:24px;border:1px solid oklch(0.45 0.04 145/.6);
  border-radius:2px;background:oklch(0.13 0.02 145/.3);display:none;
}
.result-card.show{display:block}
.result-title{font-size:.7rem;font-family:"JetBrains Mono",monospace;color:var(--moss);letter-spacing:.12em;margin-bottom:16px}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="logo">claudio<span>.fm</span></div>
    <div class="tagline mono">DJ 控制台 · live chat mode</div>
  </div>

  <!-- 輸入區 -->
  <div class="section-label">觀眾留言</div>
  <textarea class="chat-area" id="chatInput" placeholder="輸入觀眾留言，每行一條&#10;&#10;今晚加班好累&#10;失眠三個月了&#10;謝謝有你陪伴"></textarea>
  <div class="hint mono">每行一條留言，建議 3–12 條</div>
  <div class="btn-row">
    <button class="btn" id="runBtn" onclick="runPipeline()">送出給 Claudio</button>
    <span class="status-badge mono" id="statusBadge"></span>
  </div>

  <!-- 四步進度 -->
  <div class="steps" id="steps">
    <div class="step" id="step1">
      <div class="step-header">
        <span class="step-num mono">01 /</span>
        <span class="step-label">情緒分析</span>
        <span class="step-icon mono" id="icon1">—</span>
      </div>
      <div class="step-body" id="body1"></div>
    </div>
    <div class="step" id="step2">
      <div class="step-header">
        <span class="step-num mono">02 /</span>
        <span class="step-label">DJ 台詞生成</span>
        <span class="step-icon mono" id="icon2">—</span>
      </div>
      <div class="step-body" id="body2"></div>
    </div>
    <div class="step" id="step3">
      <div class="step-header">
        <span class="step-num mono">03 /</span>
        <span class="step-label">Suno 音樂生成</span>
        <span class="step-icon mono" id="icon3">—</span>
      </div>
      <div class="step-body" id="body3"></div>
    </div>
    <div class="step" id="step4">
      <div class="step-header">
        <span class="step-num mono">04 /</span>
        <span class="step-label">Claudio 開口說話</span>
        <span class="step-icon mono" id="icon4">—</span>
      </div>
      <div class="step-body" id="body4"></div>
    </div>
  </div>
</div>

<script>
let ws = null;

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (e) => handleMsg(JSON.parse(e.data));
  ws.onclose   = () => setTimeout(connect, 2000);
}

function runPipeline() {
  const text = document.getElementById('chatInput').value.trim();
  if (!text) return;
  const messages = text.split('\\n').map(s => s.trim()).filter(Boolean);
  if (!messages.length) return;

  // 重置 UI
  resetSteps();
  document.getElementById('runBtn').disabled = true;
  document.getElementById('statusBadge').textContent = '處理中...';

  ws.send(JSON.stringify({ messages }));
}

function resetSteps() {
  [1,2,3,4].forEach(i => {
    const el = document.getElementById('step'+i);
    el.className = 'step';
    document.getElementById('icon'+i).textContent = '—';
    document.getElementById('body'+i).innerHTML = '';
  });
}

function handleMsg(msg) {
  const { event, data } = msg;

  if (event === 'step') {
    const el  = document.getElementById('step' + data.step);
    const ico = document.getElementById('icon' + data.step);
    const body = document.getElementById('body' + data.step);

    if (data.status === 'running') {
      el.className = 'step running';
      ico.innerHTML = '<span class="pulse"></span>';
    }
    else if (data.status === 'waiting') {
      el.className = 'step waiting running';
      ico.innerHTML = '<span class="pulse"></span>';
      body.innerHTML = `<div class="mono" style="font-size:.78rem;color:var(--paper-faint)">${data.msg || '等待中...'}</div>`;
    }
    else if (data.status === 'done') {
      el.className = 'step done';
      ico.textContent = '✓';
      renderStepBody(data.step, data, body);
    }
  }

  if (event === 'error') {
    const step = data.step;
    if (step) {
      document.getElementById('step'+step).className = 'step error';
      document.getElementById('icon'+step).textContent = '✗';
      document.getElementById('body'+step).innerHTML =
        `<div style="color:oklch(0.6 0.1 20);font-size:.8rem;font-family:monospace">${data.msg}</div>`;
    }
  }

  if (event === 'done') {
    document.getElementById('runBtn').disabled = false;
    document.getElementById('statusBadge').textContent = '完成';
    setTimeout(() => document.getElementById('statusBadge').textContent = '', 3000);
  }
}

function renderStepBody(step, data, el) {
  if (step === 1) {
    const keywords = (data.keywords || []).map(k =>
      `<span class="tag">${k}</span>`).join('');
    el.innerHTML = `
      <div style="display:flex;gap:24px;font-size:.8rem">
        <div><span style="color:var(--paper-faint)" class="mono">氣氛</span><br/>${data.mood || '—'}</div>
        <div><span style="color:var(--paper-faint)" class="mono">情緒</span><br/>${data.emotion || '—'}</div>
      </div>
      ${keywords ? `<div class="tags" style="margin-top:10px">${keywords}</div>` : ''}
      ${data.summary ? `<div style="font-size:.85rem;color:var(--paper-dim);margin-top:10px;font-style:italic">"${data.summary}"</div>` : ''}
    `;
  }
  else if (step === 2) {
    el.innerHTML = `
      <div class="persona-badge">${data.persona || ''} · ${data.time_range || ''}</div>
      <div class="dj-script">「${data.script || ''}」</div>
    `;
  }
  else if (step === 3) {
    const url = data.music_url;
    el.innerHTML = url
      ? `<div class="music-url">🎵 <a href="${url}" target="_blank">${url}</a></div>`
      : `<div class="mono" style="font-size:.78rem;color:var(--paper-faint)">音樂生成超時，請稍後至 Suno 查詢</div>`;
  }
  else if (step === 4) {
    el.innerHTML = `
      <div class="player-wrap">
        <audio controls autoplay src="${data.audio_url}"></audio>
      </div>
      <div class="mono" style="font-size:.7rem;color:var(--paper-faint);margin-top:8px">${data.filename || ''}</div>
    `;
  }
}

connect();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("="*55)
    print("  claudio.fm 本地伺服器")
    print("  http://localhost:8000")
    print("="*55)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
