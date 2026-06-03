"""
claudio.fm 聊天室雙層過濾引擎

第一層：本地 JSON 關鍵字 Regex（<5ms，擋繁中政治/宗教/vibe-breaking）
第二層：OpenAI Moderation API（免費，擋 hate/violence/sexual/self-harm）

使用方式：
  python chat-moderator.py --text "測試留言"
"""

import os
import re
import json
import asyncio
import pathlib
from typing import Optional
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).parent.parent / ".env")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# 用 resolve() 確保跨執行環境都找得到
BLACKLIST_PATH = pathlib.Path(__file__).resolve().parent / "blacklist.json"

# DeepSeek 分類 → 友善說明
CATEGORY_LABELS = {
    "hate":       "仇恨言論",
    "violence":   "暴力威脅",
    "sexual":     "色情/性暗示",
    "self_harm":  "自我傷害",
    "harassment": "人身攻擊/騷擾",
}

REJECT_MSG = (
    "這段話似乎帶有敏感或強烈的情緒字眼。"
    "在這裡，我們希望維持一個平靜的空間，"
    "請稍微修改一下用詞再送出好嗎？"
)


class ChatModerator:
    """雙層聊天室過濾引擎"""

    def __init__(self):
        self.blacklist = self._load_blacklist()
        self.patterns  = self._compile_patterns()

    # ── 第一層：本地關鍵字 ──────────────────────────────────

    def _load_blacklist(self) -> dict:
        if not BLACKLIST_PATH.exists():
            return {}
        with open(BLACKLIST_PATH, encoding="utf-8") as f:
            return json.load(f)

    def _compile_patterns(self) -> list[tuple[str, re.Pattern]]:
        """將 blacklist.json 每個分類的詞彙編譯成 Regex Pattern"""
        patterns = []
        for category, data in self.blacklist.items():
            if category.startswith("_"):
                continue
            terms = data.get("terms", [])
            if not terms:
                continue
            escaped = [re.escape(t) for t in terms]
            pattern = re.compile("|".join(escaped), re.IGNORECASE)
            patterns.append((category, pattern))
        return patterns

    def check_layer1(self, text: str) -> dict:
        """本地關鍵字過濾，回傳毫秒內結果"""
        for category, pattern in self.patterns:
            match = pattern.search(text)
            if match:
                return {
                    "passed":   False,
                    "layer":    1,
                    "category": category,
                    "matched":  match.group(),
                    "message":  REJECT_MSG,
                }
        return {"passed": True, "layer": 1}

    # ── 第二層：DeepSeek 語意審查 ───────────────────────────

    async def check_layer2(self, text: str) -> dict:
        """DeepSeek 語意審查，擅長繁中隱晦攻擊、陰陽怪氣"""
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_key:
            return {"passed": True, "layer": 2, "note": "no deepseek key"}
        if not HTTPX_AVAILABLE:
            return {"passed": True, "layer": 2, "note": "httpx not installed"}

        prompt = f"""你是一個深夜電台聊天室的語意審查員，負責維護溫暖、靜謐的氛圍。
請判斷以下留言是否違反規則。

【禁止類別】
- hate：仇恨言論、歧視、針對特定群體的攻擊
- violence：暴力威脅、鼓勵傷害他人
- sexual：色情、性暗示、性騷擾
- self_harm：鼓勵或美化自我傷害（微妙情境）
- harassment：人身攻擊、陰陽怪氣、惡意騷擾

【留言】
{text}

只回傳 JSON，不要任何其他文字：
{{"flagged": true 或 false, "category": "hate/violence/sexual/self_harm/harassment/clean", "reason": "一句話說明"}}"""

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {deepseek_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 80,
                    },
                )

            if resp.status_code != 200:
                return {"passed": True, "layer": 2, "note": f"api_error_{resp.status_code}"}

            content = resp.json()["choices"][0]["message"]["content"].strip()

            # 解析 JSON
            import json as _json
            start, end = content.find("{"), content.rfind("}") + 1
            data = _json.loads(content[start:end]) if start >= 0 else {}

            if data.get("flagged"):
                category = data.get("category", "unknown")
                label = CATEGORY_LABELS.get(category, category)
                return {
                    "passed":   False,
                    "layer":    2,
                    "category": category,
                    "label":    label,
                    "reason":   data.get("reason", ""),
                    "message":  REJECT_MSG,
                }

            return {"passed": True, "layer": 2}

        except httpx.TimeoutException:
            return {"passed": True, "layer": 2, "note": "timeout_passthrough"}
        except Exception as e:
            return {"passed": True, "layer": 2, "note": f"error: {e}"}

    # ── 主入口 ──────────────────────────────────────────────

    async def moderate(self, text: str) -> dict:
        """
        執行雙層過濾。
        Returns:
            {
                "passed":   True/False,
                "layer":    1 or 2,   # 哪層擋住的
                "category": "...",    # 違規類別
                "message":  "...",    # 對用戶顯示的文字
            }
        """
        text = text.strip()
        if not text:
            return {"passed": False, "layer": 0, "message": "訊息不能為空"}

        # 第一層
        r1 = self.check_layer1(text)
        if not r1["passed"]:
            return r1

        # 第二層
        r2 = await self.check_layer2(text)
        return r2


# ── CLI 測試 ────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="claudio.fm 聊天審查測試")
    parser.add_argument("--text", required=True, help="要測試的留言")
    parser.add_argument("--layer1", action="store_true", help="只測第一層")
    args = parser.parse_args()

    moderator = ChatModerator()

    if args.layer1:
        result = moderator.check_layer1(args.text)
    else:
        result = asyncio.run(moderator.moderate(args.text))

    status = "✅ 通過" if result["passed"] else "🚫 攔截"
    print(f"\n{status}")
    print(f"  層級：Layer {result.get('layer', '?')}")
    if not result["passed"]:
        print(f"  類別：{result.get('category', '—')}")
        if result.get("matched"):
            print(f"  命中：{result['matched']}")
        if result.get("score"):
            print(f"  分數：{result['score']}")
        print(f"  提示：{result.get('message', '')}")
    else:
        if result.get("note"):
            print(f"  備註：{result['note']}")
    print()
