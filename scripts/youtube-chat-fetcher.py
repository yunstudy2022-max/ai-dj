"""
YouTube Live Chat Fetcher
实时抓取 YouTube 直播聊天室消息，供 claudio.fm 情绪分析使用

使用方式：
    python youtube-chat-fetcher.py --video-id YOUR_VIDEO_ID
    python youtube-chat-fetcher.py --video-id YOUR_VIDEO_ID --poll

依赖：
    pip install google-api-python-client python-dotenv
"""

import os
import time
import asyncio
import argparse
import json
import re
from typing import List, Dict, Optional, Callable, AsyncGenerator
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False


# 关键词过滤列表（垃圾、广告、机器人）
SPAM_PATTERNS = [
    r"(?i)sub.*?sub",
    r"(?i)follow.*?follow",
    r"(?i)check.*?my.*?channel",
    r"(?i)free.*?gift",
    r"(?i)giveaway",
    r"http[s]?://",
    r"(?i)discord\.gg/",
]

# 最小/最大留言长度（太短或太长的跳过）
MIN_MSG_LEN = 2
MAX_MSG_LEN = 200


class YouTubeChatFetcher:
    """YouTube Live Chat 实时抓取器"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("缺少 YOUTUBE_API_KEY，请在 .env 文件中设置")

        if not YOUTUBE_API_AVAILABLE:
            raise ImportError(
                "缺少依赖包，请运行：pip install google-api-python-client"
            )

        self.youtube = build("youtube", "v3", developerKey=self.api_key)
        self._seen_message_ids: set = set()

    # ------------------------------------------------------------------
    # 核心 API 方法
    # ------------------------------------------------------------------

    def get_live_chat_id(self, video_id: str) -> Optional[str]:
        """
        从视频 ID 取得 liveChatId。
        视频必须处于直播状态（liveBroadcastContent = live）。
        """
        response = self.youtube.videos().list(
            part="liveStreamingDetails",
            id=video_id
        ).execute()

        items = response.get("items", [])
        if not items:
            raise ValueError(f"找不到视频 {video_id}，请确认 ID 正确")

        details = items[0].get("liveStreamingDetails", {})
        chat_id = details.get("activeLiveChatId")
        if not chat_id:
            raise ValueError(
                f"视频 {video_id} 目前没有进行中的直播，"
                "请确认直播已开始且为公开/不公开状态"
            )
        return chat_id

    def fetch_messages(
        self,
        live_chat_id: str,
        page_token: Optional[str] = None,
        max_results: int = 200
    ) -> Dict:
        """
        单次拉取聊天室消息。

        Returns:
            {
                "messages": [...],
                "nextPageToken": "...",
                "pollingIntervalMillis": 5000
            }
        """
        params = dict(
            liveChatId=live_chat_id,
            part="snippet,authorDetails",
            maxResults=min(max_results, 2000)
        )
        if page_token:
            params["pageToken"] = page_token

        response = self.youtube.liveChatMessages().list(**params).execute()

        raw_items = response.get("items", [])
        messages = [self._parse_message(item) for item in raw_items]
        messages = [m for m in messages if m]  # 过滤 None（解析失败的）

        return {
            "messages": messages,
            "nextPageToken": response.get("nextPageToken"),
            "pollingIntervalMillis": response.get("pollingIntervalMillis", 5000)
        }

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def fetch_live_chat(
        self,
        video_id: str,
        limit: int = 20,
        filter_spam: bool = True
    ) -> List[Dict]:
        """
        一次性抓取直播聊天室最新消息（不持续轮询）。

        Returns:
            [
                {
                    "author": "username",
                    "text": "message content",
                    "timestamp": "2026-05-12 02:30:45",
                    "is_superchat": False
                },
                ...
            ]
        """
        chat_id = self.get_live_chat_id(video_id)
        result = self.fetch_messages(chat_id, max_results=limit * 3)
        messages = result["messages"]

        if filter_spam:
            messages = self.filter_spam(messages)

        # 只保留最新的 limit 条
        return messages[-limit:]

    def fetch_text_only(self, video_id: str, limit: int = 20) -> List[str]:
        """
        只返回纯文字列表，供 integration-engine 直接使用。
        """
        msgs = self.fetch_live_chat(video_id, limit=limit)
        return [m["text"] for m in msgs]

    async def poll_forever(
        self,
        video_id: str,
        on_batch: Callable[[List[Dict]], None],
        batch_size: int = 12,
        filter_spam: bool = True
    ):
        """
        持续轮询直播聊天室，每当积累足够留言时调用 on_batch 回调。

        Args:
            video_id:    YouTube 视频 ID
            on_batch:    回调函数，接收一批 message dicts
            batch_size:  积累多少条再触发一次回调
            filter_spam: 是否过滤垃圾留言
        """
        print(f"[YouTube] 开始轮询视频 {video_id} 的直播聊天...")
        chat_id = self.get_live_chat_id(video_id)
        print(f"[YouTube] 取得 liveChatId: {chat_id[:20]}...")

        page_token = None
        buffer: List[Dict] = []

        while True:
            try:
                result = self.fetch_messages(chat_id, page_token=page_token)
                page_token = result["nextPageToken"]
                interval_ms = result["pollingIntervalMillis"]

                new_msgs = self._deduplicate(result["messages"])
                if filter_spam:
                    new_msgs = self.filter_spam(new_msgs)

                buffer.extend(new_msgs)

                if len(buffer) >= batch_size:
                    batch = buffer[:batch_size]
                    buffer = buffer[batch_size:]
                    print(f"[YouTube] 触发批次处理（{len(batch)} 条留言）")
                    on_batch(batch)

                # 按照 YouTube 要求的间隔轮询，避免超出配额
                wait_s = max(interval_ms / 1000, 5.0)
                await asyncio.sleep(wait_s)

            except HttpError as e:
                if e.resp.status == 403:
                    print("[YouTube] ❌ API 配额已用尽，请明天再试或更换 API Key")
                    break
                print(f"[YouTube] HTTP 错误 {e.resp.status}，5 秒后重试...")
                await asyncio.sleep(5)

            except Exception as e:
                print(f"[YouTube] 错误：{e}，10 秒后重试...")
                await asyncio.sleep(10)

    # ------------------------------------------------------------------
    # 过滤与清洗
    # ------------------------------------------------------------------

    def filter_spam(self, messages: List[Dict]) -> List[Dict]:
        """过滤垃圾留言、过短/过长消息、纯表情符号消息"""
        result = []
        for msg in messages:
            text = msg.get("text", "")

            # 长度检查
            if len(text) < MIN_MSG_LEN or len(text) > MAX_MSG_LEN:
                continue

            # 垃圾模式检查
            if any(re.search(pat, text) for pat in SPAM_PATTERNS):
                continue

            result.append(msg)
        return result

    def _deduplicate(self, messages: List[Dict]) -> List[Dict]:
        """过滤已处理过的消息（防止重复推送）"""
        new_msgs = []
        for msg in messages:
            msg_id = msg.get("id")
            if msg_id and msg_id not in self._seen_message_ids:
                self._seen_message_ids.add(msg_id)
                new_msgs.append(msg)
        # 防止 seen 集合无限增长
        if len(self._seen_message_ids) > 10000:
            self._seen_message_ids = set(
                list(self._seen_message_ids)[-5000:]
            )
        return new_msgs

    # ------------------------------------------------------------------
    # 解析辅助
    # ------------------------------------------------------------------

    def _parse_message(self, item: Dict) -> Optional[Dict]:
        """将 YouTube API 原始数据解析为标准格式"""
        try:
            snippet = item.get("snippet", {})
            author = item.get("authorDetails", {})

            msg_type = snippet.get("type", "")
            # 只处理普通留言和超级留言
            if msg_type not in ("textMessageEvent", "superChatEvent"):
                return None

            if msg_type == "textMessageEvent":
                text = snippet.get("textMessageDetails", {}).get("messageText", "")
            else:
                text = snippet.get("superChatDetails", {}).get("userComment", "")

            if not text:
                return None

            published_at = snippet.get("publishedAt", "")
            if published_at:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                ts = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            else:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return {
                "id": item.get("id"),
                "author": author.get("displayName", "匿名"),
                "text": text.strip(),
                "timestamp": ts,
                "is_superchat": msg_type == "superChatEvent",
                "is_moderator": author.get("isChatModerator", False),
            }

        except Exception:
            return None


# ------------------------------------------------------------------
# CLI 入口
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="claudio.fm YouTube Chat Fetcher")
    parser.add_argument("--video-id", required=True, help="YouTube 视频 ID")
    parser.add_argument(
        "--poll", action="store_true",
        help="持续轮询模式（默认：单次抓取后退出）"
    )
    parser.add_argument(
        "--limit", type=int, default=20,
        help="单次抓取消息数量上限（默认 20）"
    )
    parser.add_argument(
        "--batch-size", type=int, default=12,
        help="轮询模式下触发批次处理的留言数量（默认 12）"
    )
    parser.add_argument(
        "--no-filter", action="store_true",
        help="关闭垃圾留言过滤"
    )
    args = parser.parse_args()

    fetcher = YouTubeChatFetcher()

    if args.poll:
        def on_batch(messages: List[Dict]):
            print(f"\n{'='*50}")
            print(f"[批次] {datetime.now().strftime('%H:%M:%S')} — {len(messages)} 条留言")
            for m in messages:
                tag = "[SC]" if m["is_superchat"] else "    "
                print(f"  {tag} {m['author']}: {m['text']}")

        asyncio.run(fetcher.poll_forever(
            video_id=args.video_id,
            on_batch=on_batch,
            batch_size=args.batch_size,
            filter_spam=not args.no_filter
        ))

    else:
        print(f"[YouTube] 单次抓取视频 {args.video_id} 的最新留言...")
        messages = fetcher.fetch_live_chat(
            args.video_id,
            limit=args.limit,
            filter_spam=not args.no_filter
        )
        print(f"[YouTube] 取得 {len(messages)} 条留言：\n")
        print(json.dumps(messages, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
