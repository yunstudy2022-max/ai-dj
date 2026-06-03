"""
claudio.fm 本机演示脚本
快速测试完整系统，无需真实 YouTube API

使用方式：
    python demo.py --quick      # 快速演示（1 轮）
    python demo.py --extended   # 完整演示（5 轮）
"""

import asyncio
import json
import sys
from datetime import datetime

# 导入所有模块
from emotion_analyzer import EmotionAnalyzer
from dj_script_generator import DJScriptGenerator
from music_generator import MusicPromptGenerator
from queue_manager import SystemOrchestrator
from integration_engine import ClaudioFMEngine


# 模拟数据库
SAMPLE_CHAT_BATCHES = [
    # 批次 1：工作疲劳
    [
        "今晚加班好累",
        "压力太大了",
        "工作一整天，困死了",
        "又是加班的一天",
        "什么时候才能休息"
    ],
    # 批次 2：深夜思考
    [
        "有点孤独",
        "不知道在想什么",
        "感觉迷茫了",
        "心情不太好",
        "需要一些陪伴"
    ],
    # 批次 3：治愈时刻
    [
        "听你的电台心情好多了",
        "谢谢你们的陪伴",
        "感觉被治愈了",
        "好喜欢这个电台",
        "每晚都来听"
    ],
    # 批次 4：互动反馈
    [
        "有没有人在线",
        "晚安各位",
        "明天继续加油",
        "静静地陪伴就很好了",
        "音乐真的很舒服"
    ],
    # 批次 5：温暖结尾
    [
        "这是我的精神食粮",
        "感谢这个温暖的地方",
        "希望明天是美好的一天",
        "大家都加油哈",
        "晚安，谢谢陪伴"
    ]
]


class ClaudioFMDemo:
    """claudio.fm 本机演示"""

    def __init__(self, quick: bool = False):
        """
        初始化演示

        Args:
            quick: 快速模式（只演示 1 轮）
        """
        self.quick = quick
        self.batch_count = 1 if quick else len(SAMPLE_CHAT_BATCHES)
        self.engine = None
        self.current_batch = 0

    async def setup(self) -> bool:
        """初始化系统"""
        print("\n" + "="*80)
        print("🎬 claudio.fm 本机演示")
        print("="*80)

        print("\n📦 初始化后端引擎...")
        self.engine = ClaudioFMEngine()

        # 检查模块状态
        status = self.engine.get_system_status()
        print(f"\n✅ 模块状态检查：")
        for module, state in status["modules"].items():
            if state == "✅":
                print(f"   {module}: {state}")
            else:
                print(f"   {module}: {state} ⚠️ 需要配置")

        # 检查关键模块
        if self.engine.emotion_analyzer is None:
            print("\n⚠️  提示：DeepSeek API 未配置")
            print("   编辑 .env 文件，填入 DEEPSEEK_API_KEY")
            return False

        if self.engine.dj_generator is None:
            print("\n⚠️  提示：Claude API 未配置")
            print("   编辑 .env 文件，填入 CLAUDE_API_KEY")
            return False

        print("\n✅ 系统初始化成功")
        return True

    async def process_batch(self, batch_num: int):
        """处理一个聊天批次"""
        self.current_batch = batch_num
        messages = SAMPLE_CHAT_BATCHES[batch_num]

        print(f"\n" + "="*80)
        print(f"📨 批次 {batch_num + 1}/{self.batch_count}")
        print("="*80)

        # 显示聊天消息
        print(f"\n💬 接收到 {len(messages)} 条聊天消息：")
        for i, msg in enumerate(messages, 1):
            print(f"   {i}. {msg}")

        # 处理
        print(f"\n⚙️  处理流程：")
        result = await self.engine.process_youtube_chat_batch(
            messages=messages,
            time_period="late_night"
        )

        # 显示结果
        if result["status"] == "success":
            await self._display_results(result)
        else:
            print(f"\n❌ 处理失败：{result.get('error')}")

    async def _display_results(self, result: dict):
        """显示处理结果"""
        print(f"\n✅ 处理成功")

        # 1. 情绪分析结果
        emotion = result["emotion_analysis"]
        print(f"\n📊 [1/4] 情绪分析")
        print(f"   整体气氛：{emotion.get('overall_mood')}")
        print(f"   主导情绪：{emotion.get('dominant_emotion')}")
        print(f"   关键词：{', '.join(emotion.get('keywords', [])[:3])}")
        print(f"   信心度：{emotion.get('confidence', 0):.1%}")

        # 2. DJ 文案
        print(f"\n📻 [2/4] DJ 文案生成【{result['persona']}】")
        script = result["dj_script"]
        print(f"   \"{script}\"")
        print(f"   字数：{len(script)}")

        # 3. 音乐参数
        print(f"\n🎵 [3/4] 音乐生成参数")
        music_prompt = result["music_prompt"]
        print(f"   提示词：{music_prompt[:70]}...")
        print(f"   缓存：{'✅ 已有' if result['is_music_cached'] else '❌ 新建'}")

        # 4. 异步队列
        print(f"\n⚙️  [4/4] 异步队列管理")
        queue = result["queue_status"]
        print(f"   生成策略：{result['generation_strategy']}")
        print(f"   队列项目：{len(queue)} 个")

        print(f"\n⏱️  时间线规划：")
        for key, value in result["timeline"].items():
            print(f"   • {key}: {value}")

    async def run(self):
        """运行演示"""
        if not await self.setup():
            print("\n❌ 系统初始化失败，请检查 .env 配置")
            return

        print(f"\n🎬 开始演示 ({self.batch_count} 轮)")
        print(f"   时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 处理每个批次
        for i in range(self.batch_count):
            await self.process_batch(i)

            # 批次间延迟
            if i < self.batch_count - 1:
                print(f"\n⏳ 等待下一批聊天（模拟 5 秒采样间隔）...")
                await asyncio.sleep(2)

        # 总结
        self._print_summary()

    def _print_summary(self):
        """打印演示总结"""
        print(f"\n" + "="*80)
        print("✅ 演示完成")
        print("="*80)

        print(f"""
📋 演示总结：
   • 完成批次：{self.batch_count}
   • 总聊天消息：{sum(len(batch) for batch in SAMPLE_CHAT_BATCHES[:self.batch_count])}
   • 处理流程：情绪分析 → DJ 文案 → 音乐参数 → 异步队列
   • 系统状态：✅ 正常

🎯 接下来的步骤：
   1. 运行完整压力测试
      python scripts/stress-test.py --duration 5

   2. 配置 OBS 推流
      python scripts/test-obs.py

   3. 准备 YouTube 直播集成
      - 获取 YouTube API 凭证
      - 实现 Task 2.1（YouTube Chat API）

📚 相关文档：
   • 完整总结：PHASE-2-SUMMARY.md
   • OBS 配置：OBS-SETUP.md
   • 压力测试：STRESS-TEST-GUIDE.md

🎬 系统已准备就绪，可以进行真实直播了！
""")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="claudio.fm 本机演示")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="快速演示（1 轮）"
    )
    parser.add_argument(
        "--extended",
        action="store_true",
        help="完整演示（5 轮）"
    )

    args = parser.parse_args()

    # 默认快速模式
    quick_mode = not args.extended

    demo = ClaudioFMDemo(quick=quick_mode)
    await demo.run()


if __name__ == "__main__":
    asyncio.run(main())
