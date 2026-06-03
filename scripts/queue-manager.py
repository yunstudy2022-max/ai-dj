"""
Task 2.5 — 异步处理队列管理器
解决 API 延迟问题，保证直播连续性

核心问题：
  T=0s   DJ开始讲话
  T=2s   后台发送音乐生成请求
  T=5s   DJ讲完，但音乐还在生成
  T=5-60s 播放过渡音乐（雨声、翻书声等）
  T=60s  音乐生成完毕，无缝切换

使用方式：
  python queue-manager.py --test
"""

import os
import json
import time
import uuid
import asyncio
from typing import Dict, List, Callable, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()


class AudioItemStatus(Enum):
    """音频项目的状态"""
    PENDING = "pending"           # 等待处理
    GENERATING = "generating"     # 正在生成
    READY = "ready"               # 已就绪
    PLAYING = "playing"           # 播放中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


@dataclass
class AudioItem:
    """音频项目"""
    id: str
    type: str  # "dj_speech", "suno_music", "fallback_audio"
    content: Dict  # {text, mood, etc.} or {music_id, prompt, etc.}
    status: AudioItemStatus = AudioItemStatus.PENDING
    created_at: str = None
    started_at: str = None
    completed_at: str = None
    error_message: str = None
    duration_seconds: float = None  # 预计时长

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        return data


class FallbackAudioLibrary:
    """过渡音乐库"""

    FALLBACK_AUDIOS = {
        "rain": {
            "name": "下雨声",
            "duration": 30,
            "mood": ["melancholic", "introspective"],
            "path": "audio/fallback/rain.mp3"
        },
        "coffee": {
            "name": "咖啡厅环境音",
            "duration": 30,
            "mood": ["neutral", "energetic"],
            "path": "audio/fallback/coffee.mp3"
        },
        "pages": {
            "name": "翻书声",
            "duration": 20,
            "mood": ["introspective", "melancholic"],
            "path": "audio/fallback/pages.mp3"
        },
        "vinyl": {
            "name": "黑胶噪声",
            "duration": 15,
            "mood": ["melancholic", "introspective"],
            "path": "audio/fallback/vinyl.mp3"
        },
        "ambient": {
            "name": "环境音垫",
            "duration": 45,
            "mood": ["introspective", "neutral"],
            "path": "audio/fallback/ambient.mp3"
        }
    }

    @classmethod
    def get_fallback_for_mood(cls, mood: str, duration: float) -> Optional[str]:
        """
        为特定情绪选择合适的过渡音乐

        Args:
            mood: 情绪类型
            duration: 需要填充的时长（秒）

        Returns:
            fallback audio key 或 None
        """
        candidates = [
            key for key, audio in cls.FALLBACK_AUDIOS.items()
            if mood in audio["mood"]
        ]

        if not candidates:
            candidates = list(cls.FALLBACK_AUDIOS.keys())

        # 选择接近所需时长的音乐
        best_match = min(
            candidates,
            key=lambda k: abs(cls.FALLBACK_AUDIOS[k]["duration"] - duration)
        )

        return best_match


class AudioQueue:
    """异步音频队列管理器"""

    def __init__(self, max_queue_size: int = 50):
        """
        初始化队列

        Args:
            max_queue_size: 最大队列长度
        """
        self.queue: List[AudioItem] = []
        self.max_queue_size = max_queue_size
        self.current_playing: Optional[AudioItem] = None
        self.callbacks: Dict[str, List[Callable]] = {
            "item_added": [],
            "status_changed": [],
            "error": []
        }

    def add_item(self, audio_type: str, content: Dict, duration: float = None) -> str:
        """
        添加音频项目到队列

        Args:
            audio_type: 音频类型 (dj_speech / suno_music / fallback_audio)
            content: 内容字典
            duration: 预计时长（秒）

        Returns:
            音频项目 ID
        """
        if len(self.queue) >= self.max_queue_size:
            raise Exception("Queue is full")

        item = AudioItem(
            id=str(uuid.uuid4())[:8],
            type=audio_type,
            content=content,
            duration_seconds=duration
        )

        self.queue.append(item)
        self._trigger_callback("item_added", item)

        return item.id

    def update_status(self, item_id: str, status: AudioItemStatus, error: str = None):
        """
        更新音频项目状态

        Args:
            item_id: 项目 ID
            status: 新状态
            error: 错误消息（如果失败）
        """
        item = self._find_item(item_id)
        if not item:
            return

        old_status = item.status
        item.status = status
        item.error_message = error

        if status == AudioItemStatus.GENERATING:
            item.started_at = datetime.now().isoformat()
        elif status in [AudioItemStatus.COMPLETED, AudioItemStatus.FAILED]:
            item.completed_at = datetime.now().isoformat()

        self._trigger_callback("status_changed", {
            "item_id": item_id,
            "old_status": old_status.value,
            "new_status": status.value,
            "item": item
        })

        if status == AudioItemStatus.FAILED:
            self._trigger_callback("error", {"item_id": item_id, "error": error})

    def get_next_item(self) -> Optional[AudioItem]:
        """
        获取下一个就绪的音频项目

        Returns:
            就绪的音频项目或 None
        """
        for item in self.queue:
            if item.status == AudioItemStatus.READY:
                return item
        return None

    def peek_queue(self, limit: int = 5) -> List[Dict]:
        """
        查看队列中的项目（不移除）

        Args:
            limit: 返回的最大项目数

        Returns:
            队列中的项目列表
        """
        return [item.to_dict() for item in self.queue[:limit]]

    def _find_item(self, item_id: str) -> Optional[AudioItem]:
        """查找项目"""
        for item in self.queue:
            if item.id == item_id:
                return item
        return None

    def _trigger_callback(self, event: str, data: any):
        """触发回调函数"""
        for callback in self.callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Callback error: {e}")

    def register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)


class AsyncMusicGenerator:
    """异步音乐生成管理器"""

    def __init__(self, queue: AudioQueue):
        """
        初始化异步生成器

        Args:
            queue: 音频队列
        """
        self.queue = queue
        self.generating_tasks: Dict[str, Dict] = {}

    async def generate_music_async(
        self,
        item_id: str,
        prompt: str,
        mood: str,
        timeout_seconds: float = 120
    ) -> bool:
        """
        异步生成音乐（模拟）

        Args:
            item_id: 项目 ID
            prompt: 音乐提示词
            mood: 情绪
            timeout_seconds: 超时时间

        Returns:
            是否成功
        """
        self.queue.update_status(item_id, AudioItemStatus.GENERATING)

        try:
            # 模拟 Suno API 调用延迟（实际环境中这里会调用真实的 API）
            # 假设平均 30-60 秒生成
            simulated_generation_time = 45

            start_time = time.time()
            while time.time() - start_time < simulated_generation_time:
                if time.time() - start_time > timeout_seconds:
                    raise Exception("Music generation timeout")
                await asyncio.sleep(1)

            # 模拟成功
            music_id = f"suno_{uuid.uuid4().hex[:8]}"
            self.queue.update_status(item_id, AudioItemStatus.READY)
            self.generating_tasks[item_id] = {
                "music_id": music_id,
                "prompt": prompt,
                "completed_at": datetime.now().isoformat()
            }

            return True

        except Exception as e:
            self.queue.update_status(
                item_id,
                AudioItemStatus.FAILED,
                error=str(e)
            )
            return False

    async def generate_with_fallback(
        self,
        item_id: str,
        prompt: str,
        mood: str,
        dj_speech_duration: float = 10
    ) -> Dict:
        """
        生成音乐，如果超时则用过渡音乐

        Args:
            item_id: 项目 ID
            prompt: 音乐提示词
            mood: 情绪
            dj_speech_duration: DJ 讲话时长（秒）

        Returns:
            {
                "status": "ready" | "fallback",
                "main_music_id": "...",
                "fallback_audio": "...",
                "timeline": {...}
            }
        """
        # 启动异步生成任务
        generate_task = asyncio.create_task(
            self.generate_music_async(item_id, prompt, mood, timeout_seconds=60)
        )

        # 估计 DJ 讲话时长 + 缓冲
        wait_time = dj_speech_duration + 5

        try:
            # 等待生成完成，超时设为预期时长
            success = await asyncio.wait_for(
                generate_task,
                timeout=wait_time
            )

            if success:
                return {
                    "status": "ready",
                    "timeline": {
                        "dj_speech": f"0-{dj_speech_duration}s",
                        "music_starts": f"{dj_speech_duration}s"
                    }
                }

        except asyncio.TimeoutError:
            # 音乐还没生成，启用过渡音乐
            fallback_key = FallbackAudioLibrary.get_fallback_for_mood(mood, 30)

            # 继续生成音乐（后台）
            # generate_task 继续运行，生成完成后自动替换

            return {
                "status": "fallback",
                "fallback_audio": fallback_key,
                "timeline": {
                    "dj_speech": f"0-{dj_speech_duration}s",
                    "fallback_audio": f"{dj_speech_duration}-{dj_speech_duration + 30}s",
                    "music_expected": f"{dj_speech_duration + 30}s (when ready)"
                }
            }

    def get_task_status(self, item_id: str) -> Dict:
        """获取任务状态"""
        item = self.queue._find_item(item_id)
        if not item:
            return {}

        return {
            "item_id": item_id,
            "status": item.status.value,
            "duration": item.duration_seconds,
            "created_at": item.created_at,
            "started_at": item.started_at,
            "completed_at": item.completed_at,
            "generation_info": self.generating_tasks.get(item_id, {})
        }


class SystemOrchestrator:
    """系统协调器 — 整合情绪分析、文案生成、音乐生成"""

    def __init__(self):
        """初始化系统"""
        self.queue = AudioQueue()
        self.async_generator = AsyncMusicGenerator(self.queue)

    async def process_chat_batch(
        self,
        messages: List[str],
        mood_analysis: Dict,
        dj_script: str,
        music_prompt: str
    ) -> Dict:
        """
        处理一批聊天消息的完整流程

        Args:
            messages: 留言列表
            mood_analysis: 情绪分析结果
            dj_script: DJ 文案
            music_prompt: 音乐提示词

        Returns:
            处理结果
        """
        # 1. 添加 DJ 讲话到队列
        dj_item_id = self.queue.add_item(
            audio_type="dj_speech",
            content={"text": dj_script, "mood": mood_analysis.get("overall_mood")},
            duration=len(dj_script) * 0.05  # 估计讲话时长
        )

        # 模拟 TTS 处理
        self.queue.update_status(dj_item_id, AudioItemStatus.READY)
        dj_duration = self.queue._find_item(dj_item_id).duration_seconds

        # 2. 添加音乐生成任务（异步）
        music_item_id = self.queue.add_item(
            audio_type="suno_music",
            content={"prompt": music_prompt, "mood": mood_analysis.get("overall_mood")}
        )

        # 3. 启动异步生成，等待结果或超时
        generation_result = await self.async_generator.generate_with_fallback(
            item_id=music_item_id,
            prompt=music_prompt,
            mood=mood_analysis.get("overall_mood"),
            dj_speech_duration=dj_duration
        )

        # 4. 如果需要，添加过渡音乐
        if generation_result["status"] == "fallback":
            fallback_key = generation_result["fallback_audio"]
            fallback_item_id = self.queue.add_item(
                audio_type="fallback_audio",
                content={"key": fallback_key},
                duration=FallbackAudioLibrary.FALLBACK_AUDIOS[fallback_key]["duration"]
            )
            self.queue.update_status(fallback_item_id, AudioItemStatus.READY)

        return {
            "dj_item_id": dj_item_id,
            "music_item_id": music_item_id,
            "generation_strategy": generation_result["status"],
            "timeline": generation_result.get("timeline", {}),
            "queue_status": self.queue.peek_queue(limit=5)
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Queue Manager")
    parser.add_argument("--test", action="store_true", help="Run test")

    args = parser.parse_args()

    if args.test:
        print("\n" + "="*60)
        print("Queue Manager 测试")
        print("="*60)

        async def run_test():
            orchestrator = SystemOrchestrator()

            # 模拟数据
            messages = ["今晚加班好累", "同感压力大"]
            mood_analysis = {
                "overall_mood": "melancholic",
                "dominant_emotion": "tired",
                "keywords": ["work", "sleep"]
            }
            dj_script = "有时候，靜靜聽著就夠了。Yuki，看你加班这么辛苦，这首曲子就献给今晚还醒著的你。"
            music_prompt = "Lo-Fi hip hop, melancholic piano, vinyl crackle, slow drums"

            result = await orchestrator.process_chat_batch(
                messages, mood_analysis, dj_script, music_prompt
            )

            print(f"\n处理结果：")
            print(f"生成策略：{result['generation_strategy']}")
            print(f"时间线：{json.dumps(result['timeline'], ensure_ascii=False, indent=2)}")
            print(f"\n队列状态：")
            for item in result['queue_status']:
                print(f"  [{item['id']}] {item['type']}: {item['status']}")

        asyncio.run(run_test())
