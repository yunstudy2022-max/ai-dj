"""
DJ 創歌完整流程測試
模擬：觀眾聊天 → 情緒分析 → DJ 台詞 → Suno 生成音樂

使用方式：
  python test-dj-creates-song.py                   # 模擬聊天
  python test-dj-creates-song.py --video-id ID     # 真實 YouTube 聊天
  python test-dj-creates-song.py --skip-suno       # 跳過 Suno（只測試前三步）
"""

import os
import sys
import json
import time
import asyncio
import argparse
import importlib.util
import pathlib
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


# ── 模組載入（處理檔名含連字符）──────────────────────────────
def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    src = pathlib.Path(__file__).parent / filename
    spec = importlib.util.spec_from_file_location(name, src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── 模擬聊天資料庫 ──────────────────────────────────────────
MOCK_CHATS = {
    "sad": [
        "今天被主管罵了，好沮喪",
        "失戀三個月了，還是走不出來",
        "一個人吃飯已經習慣了，但還是很孤單",
        "熬夜趕報告，不知道撐得過去嗎",
        "好想有人陪",
    ],
    "chill": [
        "剛洗完澡，窩在被窩聽音樂",
        "泡茶配電台，完美的夜晚",
        "今天收工早，難得放鬆一下",
        "外面在下雨，剛好",
        "感覺整個人慢下來了",
    ],
    "mixed": [
        "工作好累但音樂救了我",
        "有點難過，但還好有你們陪",
        "今天有好事也有壞事，整體還行",
        "失眠中，腦子停不下來",
        "感謝這個電台，讓我安心一點",
    ],
}


# ── Step 1：情緒分析 ─────────────────────────────────────────
def step_emotion(messages: list) -> dict:
    print("\n" + "─"*55)
    print("STEP 1 / 3  情緒分析（DeepSeek）")
    print("─"*55)
    for m in messages:
        print(f"  💬 {m}")

    m = _load("emotion_analyzer", "emotion-analyzer.py")
    analyzer = m.EmotionAnalyzer()

    t0 = time.time()
    result = analyzer.analyze_batch(messages)
    elapsed = time.time() - t0

    print(f"\n  ✅ 完成（{elapsed:.1f}s）")
    print(f"  整體氣氛：{result.get('overall_mood')}")
    print(f"  主導情緒：{result.get('dominant_emotion')}")
    print(f"  關鍵詞：{', '.join(result.get('keywords', []))}")
    if result.get("summary"):
        print(f"  摘要：{result['summary']}")

    return result


# ── Step 2：DJ 台詞 ──────────────────────────────────────────
def step_dj_script(mood_analysis: dict) -> dict:
    print("\n" + "─"*55)
    print("STEP 2 / 3  DJ 台詞生成（DeepSeek）")
    print("─"*55)

    m = _load("dj_script_generator", "dj-script-generator.py")
    generator = m.DJScriptGenerator()

    t0 = time.time()
    result = generator.generate_script(mood_analysis=mood_analysis)
    elapsed = time.time() - t0

    print(f"\n  ✅ 完成（{elapsed:.1f}s）")
    print(f"  人設：{result['persona']}（{result['time_range']}）")
    print(f"\n  📻 DJ 台詞：")
    print(f"  「{result['script']}」")

    return result


# ── Step 4：ElevenLabs TTS ───────────────────────────────────
def step_tts(dj_result: dict, auto_play: bool = True) -> str:
    print("\n" + "─"*55)
    print("STEP 4 / 4  Claudio 開口說話（ElevenLabs TTS）")
    print("─"*55)

    m = _load("elevenlabs_tts", "elevenlabs-tts.py")
    tts = m.ElevenLabsTTS()

    # 查剩餘配額（需要 user_read 權限，失敗不影響 TTS）
    try:
        q = tts.get_quota()
        if q.get("remaining") is not None:
            print(f"  配額：剩餘 {q['remaining']:,} 字符（{q.get('tier')}）")
    except Exception:
        pass

    script = dj_result["script"]
    period = dj_result.get("persona", "midnight")
    # 人設名稱 → 時段 key
    period_map = {"晚安下班了": "evening", "深夜吧檯": "midnight", "I人的时光": "late_night"}
    period_key = period_map.get(period, "midnight")

    print(f"  時段語氣：{period}（{period_key}）")
    print(f"  台詞：「{script}」")

    import time as _time
    t0 = _time.time()
    path = tts.speak_with_retry(
        text=script,
        time_period=period_key,
        auto_play=auto_play
    )
    elapsed = _time.time() - t0

    print(f"\n  ✅ 生成完成（{elapsed:.1f}s）")
    print(f"  📁 音檔：{path}")
    return path


# ── Step 3：Suno 生成音樂 ────────────────────────────────────
def step_suno(mood_analysis: dict, dj_result: dict) -> dict:
    print("\n" + "─"*55)
    print("STEP 3 / 3  音樂生成（Suno API）")
    print("─"*55)

    # 先建構音樂提示詞
    mp = _load("music_generator", "music-generator.py")
    gen = mp.MusicPromptGenerator()
    prompt_data = gen.generate_prompt(
        mood=mood_analysis.get("overall_mood", "neutral"),
        time_period=_time_period(),
        keywords=mood_analysis.get("keywords", [])[:3]
    )

    print(f"  🎵 音樂提示詞：")
    print(f"  {prompt_data['prompt'][:80]}...")
    print(f"  風格：{prompt_data['style']}｜BPM：{prompt_data['bpm']}")

    # 呼叫 Suno API
    suno_client = _load("suno_client", "suno-client.py")
    client = suno_client.SunoClient()

    t0 = time.time()
    job = client.generate(
        prompt=prompt_data["prompt"],
        title=f"claudio.fm × {dj_result['persona']}",
        make_instrumental=True
    )
    elapsed = time.time() - t0

    if job.get("status") == "error":
        print(f"\n  ❌ Suno 錯誤：{job.get('error')}")
        return job

    print(f"\n  ✅ 任務建立（{elapsed:.1f}s）")
    print(f"  task_id：{job.get('task_id')}")
    print(f"  狀態：{job.get('status', 'submitted')}")

    # 輪詢等待（最多 3 分鐘，約 30-40s 可得 stream_url）
    task_id = job.get("task_id")
    if task_id:
        print("\n  ⏳ 等待 Suno 生成（stream_url 約 30-40s）...")
        audio_url = client.wait_for_audio(task_id, timeout=180)
        if audio_url:
            print(f"\n  🎶 音樂生成完成！")
            print(f"  URL：{audio_url}")
            job["audio_url"] = audio_url
        else:
            print("\n  ⚠️  超時，音樂仍在生成中，稍後可用 task_id 查詢")

    return job


# ── 主流程 ───────────────────────────────────────────────────
def run(messages: list, skip_suno: bool = False):
    print("\n" + "="*55)
    print("  claudio.fm × DJ 創歌完整流程")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)

    # Step 1
    try:
        mood = step_emotion(messages)
    except Exception as e:
        print(f"\n❌ 情緒分析失敗：{e}")
        return

    # Step 2
    try:
        dj = step_dj_script(mood)
    except Exception as e:
        print(f"\n❌ DJ 台詞失敗：{e}")
        return

    # Step 3
    if skip_suno:
        print("\n" + "─"*55)
        print("STEP 3 / 4  Suno 生成（已跳過，--skip-suno）")
        print("─"*55)
    else:
        try:
            suno = step_suno(mood, dj)
        except FileNotFoundError:
            print("\n  ❌ 找不到 suno-client.py，請先確認檔案存在")
        except Exception as e:
            print(f"\n  ❌ Suno 生成失敗：{e}")

    # Step 4
    try:
        step_tts(dj, auto_play=True)
    except Exception as e:
        print(f"\n  ❌ TTS 失敗：{e}")

    print("\n" + "="*55)
    print("  流程完成")
    print("="*55)


def _time_period() -> str:
    h = datetime.now().hour
    if 18 <= h < 21:
        return "evening"
    elif 21 <= h < 24:
        return "midnight"
    return "late_night"


# ── CLI ─────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DJ 創歌完整流程測試")
    parser.add_argument("--video-id", help="YouTube 直播 ID（不填則用模擬留言）")
    parser.add_argument(
        "--mood", default="mixed",
        choices=["sad", "chill", "mixed"],
        help="模擬留言的情緒類型（預設：mixed）"
    )
    parser.add_argument(
        "--skip-suno", action="store_true",
        help="跳過 Suno API 呼叫（只測試前兩步）"
    )
    args = parser.parse_args()

    if args.video_id:
        yt = _load("youtube_chat_fetcher", "youtube-chat-fetcher.py")
        fetcher = yt.YouTubeChatFetcher()
        print(f"[YouTube] 抓取直播留言...")
        messages = fetcher.fetch_text_only(args.video_id, limit=12)
        if not messages:
            print("❌ 沒有抓到留言，改用模擬資料")
            messages = MOCK_CHATS[args.mood]
    else:
        messages = MOCK_CHATS[args.mood]
        print(f"[模擬] 使用 {args.mood} 情緒的測試留言")

    run(messages, skip_suno=args.skip_suno)
