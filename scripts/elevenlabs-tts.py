"""
ElevenLabs TTS 客戶端 — Claudio 的聲音引擎
讓 Claudio 真正開口說話

API 文件：https://elevenlabs.io/docs/api-reference/text-to-speech/convert

使用方式：
  python elevenlabs-tts.py --text "今晚的空气有点重，我陪你听完这首歌。"
  python elevenlabs-tts.py --text "..." --play   # 生成後自動播放

在 .env 設定：
  ELEVENLABS_API_KEY=你的key
  ELEVENLABS_VOICE_ID=（選填，預設用 Adam）
"""

import os
import re
import time
import subprocess
import pathlib
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ── 可選主持人音色 ────────────────────────────────────────────
VOICE_ROSTER = {
    "claudio": "kbrsaic1zriFXx1pgRYN", # Claudio（試用）
    "aj":      "9lHjugDhwqoxA5MhX0az", # AJ（備用 A）
    "adam":    "pNInz6obpgDQGcFmaJgB", # Adam（備用 B）
}
DEFAULT_VOICE_ID = VOICE_ROSTER["claudio"]

# 三個時段的語音參數
PERSONA_VOICE_SETTINGS = {
    "evening": {          # 晚安下班了：溫暖有活力
        "stability": 0.45,
        "similarity_boost": 0.80,
        "style": 0.30,
        "speed": 1.05,
    },
    "midnight": {         # 深夜吧檯：低沉故事感
        "stability": 0.35,
        "similarity_boost": 0.75,
        "style": 0.50,
        "speed": 0.90,
    },
    "late_night": {       # I人的時光：輕聲細語
        "stability": 0.65,
        "similarity_boost": 0.70,
        "style": 0.10,
        "speed": 0.80,
    },
}

OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "audio_output"


class ElevenLabsTTS:
    """Claudio 語音合成引擎"""

    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(self, api_key: str = None, voice_id: str = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "缺少 ELEVENLABS_API_KEY，請在 .env 中填入\n"
                "取得 Key：https://elevenlabs.io/app/settings/api-keys"
            )

        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def speak(
        self,
        text: str,
        time_period: str = None,
        output_path: str = None,
        auto_play: bool = False
    ) -> str:
        """
        將文字轉換為 Claudio 的語音，存成 mp3 檔案。

        Args:
            text:        DJ 台詞
            time_period: 時段（evening/midnight/late_night）→ 決定語氣
            output_path: 指定輸出路徑（不填則自動命名）
            auto_play:   生成後自動播放

        Returns:
            儲存的 mp3 檔案路徑
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("請安裝依賴：pip install requests")

        period = time_period or _detect_period()
        voice_settings = PERSONA_VOICE_SETTINGS.get(period, PERSONA_VOICE_SETTINGS["midnight"])

        text = _clean_for_tts(text)

        url = f"{self.BASE_URL}/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_v3",
            "voice_settings": voice_settings,
            "output_format": "mp3_44100_128",
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)

        if resp.status_code != 200:
            raise Exception(
                f"ElevenLabs API 錯誤 {resp.status_code}：{resp.text[:300]}"
            )

        # 儲存音檔
        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(OUTPUT_DIR / f"claudio_{period}_{ts}.mp3")

        with open(output_path, "wb") as f:
            f.write(resp.content)

        if auto_play:
            self._play(output_path)

        return output_path

    def speak_with_retry(
        self,
        text: str,
        time_period: str = None,
        output_path: str = None,
        auto_play: bool = False,
        retries: int = 2
    ) -> str:
        """帶重試的 speak()"""
        last_err = None
        for attempt in range(retries + 1):
            try:
                return self.speak(text, time_period, output_path, auto_play)
            except Exception as e:
                last_err = e
                if attempt < retries:
                    print(f"    ⚠️  重試 {attempt+1}/{retries}...")
                    time.sleep(2)
        raise last_err

    def list_voices(self) -> list:
        """列出帳號可用的所有聲音"""
        resp = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": self.api_key},
            timeout=15
        )
        if resp.status_code != 200:
            raise Exception(f"無法取得聲音列表：{resp.status_code}")
        return resp.json().get("voices", [])

    def get_quota(self) -> dict:
        """查詢剩餘字符配額"""
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": self.api_key},
            timeout=10
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        sub = data.get("subscription", {})
        used = sub.get("character_count", 0)
        limit = sub.get("character_limit", 0)
        return {
            "used": used,
            "limit": limit,
            "remaining": limit - used,
            "tier": sub.get("tier", "unknown")
        }

    @staticmethod
    def _play(file_path: str):
        """Windows 上用預設播放器播放 mp3"""
        try:
            os.startfile(file_path)
        except Exception:
            try:
                subprocess.Popen(["start", file_path], shell=True)
            except Exception as e:
                print(f"    ⚠️  無法自動播放：{e}")


# ── 輔助函式 ─────────────────────────────────────────────────

def _clean_for_tts(text: str) -> str:
    """清除舞台標注、修正 ElevenLabs 中文誤唸字元，再送出。"""
    # 全形括號標注：（輕聲）（停頓）等
    text = re.sub(r'（[^）]*）', '', text)
    # 半形括號內含中文的標注：(輕聲) 等；保留純英數如 (2024)
    text = re.sub(r'\([^\)]*[一-鿿][^\)]*\)', '', text)
    # ElevenLabs 已知誤唸字元修正
    _CHAR_FIX = {
        '嘿': '嗨',   # 嘿(hēi) 被唸成莫，改用嗨
        '哎': '誒',   # 哎有時唸錯
    }
    for wrong, right in _CHAR_FIX.items():
        text = text.replace(wrong, right)
    # 清理連續空白
    return re.sub(r'\s{2,}', ' ', text).strip()


def _detect_period() -> str:
    h = datetime.now().hour
    if 18 <= h < 21:
        return "evening"
    elif 21 <= h < 24:
        return "midnight"
    return "late_night"


# ── CLI ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claudio TTS 測試")
    parser.add_argument("--text", default="有時候，靜靜聽著就夠了。我在這裡。")
    parser.add_argument(
        "--period",
        choices=["evening", "midnight", "late_night"],
        help="時段（不填則依當前時間自動判斷）"
    )
    parser.add_argument("--play", action="store_true", help="生成後自動播放")
    parser.add_argument("--voices", action="store_true", help="列出可用聲音")
    parser.add_argument("--quota", action="store_true", help="查詢字符配額")
    args = parser.parse_args()

    try:
        tts = ElevenLabsTTS()

        if args.quota:
            q = tts.get_quota()
            if q:
                print(f"\n字符配額：{q.get('used', 0):,} / {q.get('limit', 0):,}")
                print(f"剩餘：{q.get('remaining', 0):,} 字符")
                print(f"方案：{q.get('tier', 'unknown')}")
            else:
                print("\n⚠️  無法查詢配額（API Key 缺少 user_read 權限，但 TTS 功能正常）")

        elif args.voices:
            voices = tts.list_voices()
            print(f"\n可用聲音（共 {len(voices)} 個）：")
            for v in voices:
                print(f"  {v['name']:20s} ID: {v['voice_id']}")

        else:
            period = args.period or _detect_period()
            print(f"\n[TTS] 時段：{period}")
            print(f"[TTS] 台詞：{args.text}")
            print(f"[TTS] 聲音：{tts.voice_id}")

            t0 = time.time()
            path = tts.speak(
                text=args.text,
                time_period=period,
                auto_play=args.play
            )
            elapsed = time.time() - t0

            print(f"\n✅ 生成完成（{elapsed:.1f}s）")
            print(f"📁 檔案：{path}")
            if not args.play:
                print("   加上 --play 可自動播放")

    except Exception as e:
        print(f"❌ {e}")
