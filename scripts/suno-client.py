"""
Suno API 客戶端（sunoapi.org 版）
文件：https://docs.sunoapi.org/suno-api/generate-music

使用方式：
  在 .env 設定：
    SUNO_API_KEY=你的key
    SUNO_BASE_URL=https://api.sunoapi.org

  python suno-client.py --prompt "lo-fi hip hop, melancholic piano"
"""

import os
import time
import json
import requests
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# sunoapi.org 的狀態碼
SUCCESS_STATES = {"SUCCESS"}
FAIL_STATES = {
    "CREATE_TASK_FAILED",
    "GENERATE_AUDIO_FAILED",
    "CALLBACK_EXCEPTION",
    "SENSITIVE_WORD_ERROR",
}


class SunoClient:
    """sunoapi.org 客戶端"""

    GENERATE_URL = "https://api.sunoapi.org/api/v1/generate"
    STATUS_URL   = "https://api.sunoapi.org/api/v1/generate/record-info"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SUNO_API_KEY")
        if not self.api_key:
            raise ValueError("缺少 SUNO_API_KEY，請在 .env 中設定")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def generate(
        self,
        prompt: str,
        title: str = "claudio.fm",
        make_instrumental: bool = True,
        model: str = "V4",
        style: str = "",
        callback_url: str = ""
    ) -> Dict:
        """
        送出音樂生成請求（非同步）。

        Returns:
            {
                "task_id": "...",
                "status": "submitted"
            }
        """
        payload = {
            "customMode": bool(style or title != "claudio.fm"),
            "instrumental": make_instrumental,
            "model": model,
            "prompt": prompt[:500],  # 非 custom mode 最多 500 字
            # callBackUrl 必填，但我們用輪詢所以填佔位 URL
            "callBackUrl": callback_url or "https://claudio.fm/callback",
        }

        if payload["customMode"]:
            if title:
                payload["title"] = title
            if style:
                payload["style"] = style

        try:
            resp = self.session.post(self.GENERATE_URL, json=payload, timeout=30)
            data = resp.json()

            if resp.status_code != 200 or data.get("code") != 200:
                return {
                    "status": "error",
                    "error": f"HTTP {resp.status_code} / code {data.get('code')}: {data.get('msg', resp.text[:200])}"
                }

            task_id = data.get("data", {}).get("taskId")
            return {
                "task_id": task_id,
                "status": "submitted",
                "raw": data
            }

        except requests.exceptions.ConnectionError:
            return {"status": "error", "error": f"無法連線到 {self.GENERATE_URL}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_status(self, task_id: str) -> Dict:
        """
        查詢生成狀態。

        Returns:
            {
                "status": "SUCCESS" | "PENDING" | ...,
                "audio_url": "https://...",      # 完成才有
                "stream_url": "https://...",
                "clips": [...]
            }
        """
        try:
            resp = self.session.get(
                self.STATUS_URL,
                params={"taskId": task_id},
                timeout=15
            )
            data = resp.json()

            if resp.status_code != 200 or data.get("code") != 200:
                return {"status": "error", "error": data.get("msg")}

            record = data.get("data", {})
            status = record.get("status", "PENDING")

            # 從 sunoData 陣列取出第一首的 URL
            suno_data = record.get("response", {}).get("sunoData", [])
            audio_url = None
            stream_url = None
            if suno_data:
                audio_url  = suno_data[0].get("audioUrl")
                stream_url = suno_data[0].get("streamAudioUrl")

            return {
                "status": status,
                "audio_url": audio_url,
                "stream_url": stream_url,
                "clips": suno_data,
                "raw": record
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def download_audio(self, url: str, save_path: str) -> str:
        """從 URL 下載音樂並儲存成 MP3，回傳存檔路徑"""
        import pathlib
        pathlib.Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        resp = self.session.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=16384):
                if chunk:
                    f.write(chunk)
        return save_path

    def wait_for_audio(
        self,
        task_id: str,
        timeout: int = 180,
        interval: int = 10
    ) -> Optional[str]:
        """
        輪詢直到音樂生成完成，回傳 stream_url（~30s）或 audio_url（~2-3min）。
        超時回傳 None。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            info = self.get_status(task_id)
            status = info.get("status", "")

            # 優先用 stream_url（快 30-40s 就有）
            url = info.get("stream_url") or info.get("audio_url")

            print(f"    [{time.strftime('%H:%M:%S')}] 狀態：{status}", end="")
            if status in SUCCESS_STATES and url:
                print(f"\n    stream_url: {url[:60]}...")
                return url
            if status in FAIL_STATES:
                print(f"\n    ❌ 失敗：{info.get('error') or status}")
                return None

            remaining = int(deadline - time.time())
            print(f"（剩餘 {remaining}s）")
            time.sleep(interval)

        return None


# ── CLI ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Suno API 客戶端測試")
    parser.add_argument(
        "--prompt",
        default="Lo-Fi hip hop, melancholic piano, strings, 70 BPM, no vocals, introspective"
    )
    parser.add_argument("--title", default="claudio.fm test")
    parser.add_argument("--model", default="V4", choices=["V4", "V4_5", "V5", "V5_5"])
    parser.add_argument("--wait", action="store_true", help="等待生成完成")
    args = parser.parse_args()

    try:
        client = SunoClient()
        print(f"[Suno] 提示詞：{args.prompt}")
        print(f"[Suno] 模型：{args.model}")

        job = client.generate(
            prompt=args.prompt,
            title=args.title,
            make_instrumental=True,
            model=args.model
        )
        print(f"\n回應：{json.dumps(job, ensure_ascii=False, indent=2)}")

        if args.wait and job.get("task_id"):
            print(f"\n[Suno] 輪詢狀態（task_id: {job['task_id']}）...")
            url = client.wait_for_audio(job["task_id"])
            if url:
                print(f"\n✅ 音樂 URL：{url}")
            else:
                print("\n⚠️  超時，請稍後手動查詢")

    except Exception as e:
        print(f"❌ {e}")
