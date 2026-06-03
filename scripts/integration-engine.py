"""
Phase 2 完整集成引擎
整合：情绪分析 → DJ 文案 → 音乐提示词 → 异步队列 → 前端推送

这是 claudio.fm 后端的核心模块

使用方式：
  python integration-engine.py --test
"""

import asyncio
import json
from typing import Dict, List
from datetime import datetime

from emotion_analyzer import EmotionAnalyzer
from dj_script_generator import DJScriptGenerator
from music_generator import MusicPromptGenerator
from queue_manager import SystemOrchestrator


class ClaudioFMEngine:
    """claudio.fm 完整后端引擎"""

    def __init__(self):
        """初始化引擎"""
        try:
            self.emotion_analyzer = EmotionAnalyzer()
            print("✅ 情绪分析引擎已加载（DeepSeek-V4）")
        except Exception as e:
            print(f"⚠️  情绪分析初始化失败: {e}")
            self.emotion_analyzer = None

        try:
            self.dj_generator = DJScriptGenerator()
            print("✅ DJ 文案生成已加载（Claude API）")
        except Exception as e:
            print(f"⚠️  DJ 生成初始化失败: {e}")
            self.dj_generator = None

        try:
            self.music_generator = MusicPromptGenerator()
            print("✅ 音乐提示词生成已加载")
        except Exception as e:
            print(f"⚠️  音乐生成初始化失败: {e}")
            self.music_generator = None

        try:
            self.orchestrator = SystemOrchestrator()
            print("✅ 异步队列系统已加载")
        except Exception as e:
            print(f"⚠️  队列系统初始化失败: {e}")
            self.orchestrator = None

    async def process_youtube_chat_batch(
        self,
        messages: List[str],
        time_period: str = None
    ) -> Dict:
        """
        处理一批 YouTube 聊天消息的完整流程

        Args:
            messages: 留言列表（最多 12 条）
            time_period: 时段（evening/midnight/late_night）

        Returns:
            {
                "status": "success",
                "emotion_analysis": {...},
                "dj_script": "...",
                "music_prompt": "...",
                "queue_status": {...},
                "timeline": {...}
            }
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "message_count": len(messages),
            "status": "processing"
        }

        try:
            # 第一步：情绪分析
            print(f"\n📊 [Step 1/4] 分析 {len(messages)} 条留言的情绪...")
            if not self.emotion_analyzer:
                raise Exception("情绪分析引擎未初始化")

            mood_analysis = self.emotion_analyzer.analyze_batch(messages)
            result["emotion_analysis"] = mood_analysis
            print(f"   ✅ 情绪分析完成：{mood_analysis.get('overall_mood')}")

            # 第二步：DJ 文案生成
            print(f"\n📻 [Step 2/4] 生成 DJ 文案...")
            if not self.dj_generator:
                raise Exception("DJ 生成器未初始化")

            dj_result = self.dj_generator.generate_script(
                mood_analysis=mood_analysis,
                listener_name=None,  # 可以后续添加常客识别
                custom_message=None
            )
            result["dj_script"] = dj_result["script"]
            result["persona"] = dj_result["persona"]
            print(f"   ✅ DJ 文案生成完成（{len(dj_result['script'])} 字）")

            # 第三步：音乐生成提示词
            print(f"\n🎵 [Step 3/4] 构建音乐提示词...")
            if not self.music_generator:
                raise Exception("音乐生成器未初始化")

            music_prompts = self.music_generator.batch_generate_prompts(
                mood_analysis=mood_analysis,
                time_period=time_period
            )
            result["music_prompt"] = music_prompts[0]["prompt"]
            result["music_cache_key"] = music_prompts[0]["cache_key"]
            result["is_music_cached"] = music_prompts[0]["is_cached"]
            print(f"   ✅ 音乐提示词完成（缓存：{result['is_music_cached']}）")

            # 第四步：异步队列编排
            print(f"\n⚙️  [Step 4/4] 启动异步音乐生成和队列管理...")
            if not self.orchestrator:
                raise Exception("队列系统未初始化")

            queue_result = await self.orchestrator.process_chat_batch(
                messages=messages,
                mood_analysis=mood_analysis,
                dj_script=dj_result["script"],
                music_prompt=music_prompts[0]["prompt"]
            )
            result["queue_status"] = queue_result
            result["generation_strategy"] = queue_result["generation_strategy"]
            result["timeline"] = queue_result["timeline"]
            print(f"   ✅ 异步生成策略：{queue_result['generation_strategy']}")

            result["status"] = "success"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"\n❌ 处理失败：{e}")

        return result

    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            "timestamp": datetime.now().isoformat(),
            "modules": {
                "emotion_analyzer": "✅" if self.emotion_analyzer else "❌",
                "dj_generator": "✅" if self.dj_generator else "❌",
                "music_generator": "✅" if self.music_generator else "❌",
                "orchestrator": "✅" if self.orchestrator else "❌"
            }
        }


async def demo_full_pipeline():
    """完整管道演示"""
    print("\n" + "="*80)
    print("claudio.fm 完整管道演示")
    print("="*80)

    engine = ClaudioFMEngine()

    # 模拟 YouTube 直播聊天
    sample_messages = [
        "今晚加班好累",
        "同感，压力太大",
        "听着电台舒服多了",
        "对，陪伴很重要",
        "有时候靠这个撑过来",
        "谢谢你们",
        "晚安，明天继续加油",
        "感觉心情好多了",
        "希望每晚都有这样的陪伴",
        "这个电台真的温暖"
    ]

    print(f"\n模拟接收 {len(sample_messages)} 条 YouTube 直播聊天...")
    for i, msg in enumerate(sample_messages[:3], 1):
        print(f"  [{i}] {msg}")
    print(f"  ... 还有 {len(sample_messages) - 3} 条")

    # 处理
    result = await engine.process_youtube_chat_batch(
        messages=sample_messages,
        time_period="late_night"
    )

    # 输出结果
    if result["status"] == "success":
        print(f"\n" + "="*80)
        print("✅ 处理结果")
        print("="*80)

        print(f"\n【情绪分析】")
        emotion = result["emotion_analysis"]
        print(f"  整体气氛：{emotion.get('overall_mood')}")
        print(f"  主导情绪：{emotion.get('dominant_emotion')}")
        print(f"  关键词：{', '.join(emotion.get('keywords', []))}")

        print(f"\n【DJ 台词】【{result['persona']}】")
        print(f"  {result['dj_script']}")

        print(f"\n【音乐参数】")
        print(f"  提示词：{result['music_prompt'][:70]}...")
        print(f"  缓存：{'✅ 使用已有' if result['is_music_cached'] else '❌ 新建'}")

        print(f"\n【异步队列】")
        print(f"  生成策略：{result['generation_strategy']}")
        print(f"  时间线：")
        for key, value in result["timeline"].items():
            print(f"    • {key}: {value}")

    else:
        print(f"\n❌ 处理失败：{result.get('error')}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="claudio.fm Integration Engine")
    parser.add_argument("--test", action="store_true", help="Run demo")

    args = parser.parse_args()

    if args.test:
        asyncio.run(demo_full_pipeline())
    else:
        engine = ClaudioFMEngine()
        print("\n系统已准备就绪")
        print(json.dumps(engine.get_system_status(), indent=2))
