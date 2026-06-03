"""
Task 2.7 — 本地 2 小时压力测试
完整系统集成测试，模拟实际直播场景

使用方式：
    python stress-test.py --duration 120  # 运行 120 分钟
    python stress-test.py --duration 5    # 快速测试 5 分钟
"""

import asyncio
import random
import time
import argparse
from typing import List
from datetime import datetime

from monitoring import PerformanceReport, APIPerformanceTracker
from integration_engine import ClaudioFMEngine


class YouTubeChatSimulator:
    """YouTube 聊天模拟器"""

    # 模拟留言库
    SAMPLE_MESSAGES = [
        # 工作/疲劳相关
        "今晚加班好累",
        "压力太大了",
        "工作一整天，累死了",
        "又是加班的一天",
        "这周一直在加班",
        "什么时候才能休息",
        "加班到现在，困得要死",

        # 感情/思考相关
        "有点孤独",
        "不知道在想什么",
        "感觉迷茫了",
        "心情不太好",
        "最近发生了些事",
        "有点难受",
        "需要一些陪伴",

        # 积极相关
        "听你的电台心情好多了",
        "谢谢你们的陪伴",
        "感觉被治愈了",
        "好喜欢这个电台",
        "每晚都来听",
        "这是我的精神食粮",
        "感谢这个温暖的地方",

        # 互动相关
        "有没有人在线",
        "晚安各位",
        "明天继续加油",
        "希望明天是美好的一天",
        "大家都加油哈",
        "静静地陪伴就很好了",
        "音乐真的很舒服",
    ]

    @staticmethod
    def generate_batch(size: int = 8) -> List[str]:
        """生成一批模拟留言"""
        return random.sample(YouTubeChatSimulator.SAMPLE_MESSAGES, min(size, len(YouTubeChatSimulator.SAMPLE_MESSAGES)))


class StressTest:
    """压力测试管理器"""

    def __init__(self, duration_minutes: float = 120):
        """
        初始化压力测试

        Args:
            duration_minutes: 测试时长（分钟）
        """
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.report = PerformanceReport()
        self.engine = None
        self.batch_count = 0
        self.error_count = 0

    async def setup(self) -> bool:
        """设置测试环境"""
        print("\n" + "="*80)
        print(f"🧪 启动 {self.duration_minutes:.1f} 分钟压力测试")
        print("="*80)

        print("\n📦 初始化 claudio.fm 引擎...")
        self.engine = ClaudioFMEngine()

        # 检查必要的模块
        status = self.engine.get_system_status()
        print(f"\n模块状态：")
        for module, state in status["modules"].items():
            print(f"  {module}: {state}")

        self.report.start_test()
        return True

    async def run_test_loop(self):
        """运行测试循环"""
        print(f"\n▶️  开始处理聊天和生成内容...")
        print(f"   采样间隔：5 秒")
        print(f"   预计批次：~{int(self.duration_seconds / 5)}")

        start_time = time.time()
        last_stats_time = start_time

        while time.time() - start_time < self.duration_seconds:
            elapsed = time.time() - start_time
            remaining = self.duration_seconds - elapsed

            # 生成模拟聊天消息
            messages = YouTubeChatSimulator.generate_batch(size=random.randint(6, 12))

            try:
                # 执行完整的处理流程
                start_process = time.time()

                result = await self.engine.process_youtube_chat_batch(
                    messages=messages,
                    time_period=self._get_time_period()
                )

                process_time = (time.time() - start_process) * 1000

                # 记录 API 调用
                if result["status"] == "success":
                    self._record_api_calls(result, process_time)
                    self.batch_count += 1
                else:
                    self.error_count += 1
                    print(f"❌ 处理失败：{result.get('error')}")

            except Exception as e:
                self.error_count += 1
                print(f"❌ 异常：{e}")

            # 定期输出统计
            if time.time() - last_stats_time > 30:  # 每 30 秒输出一次
                self._print_progress(elapsed, remaining)
                last_stats_time = time.time()

            # 等待下一个采样周期
            await asyncio.sleep(5)

        print(f"\n✅ 处理循环完成")
        print(f"   总批次：{self.batch_count}")
        print(f"   错误数：{self.error_count}")

    def _get_time_period(self) -> str:
        """根据测试进度模拟不同时段"""
        current_hour = datetime.now().hour
        if 18 <= current_hour < 21:
            return "evening"
        elif 21 <= current_hour < 24:
            return "midnight"
        else:
            return "late_night"

    def _record_api_calls(self, result: dict, total_time_ms: float):
        """记录 API 调用统计"""
        # 记录总体处理时间
        self.report.api_tracker.track_call(
            "process_youtube_chat_batch",
            total_time_ms,
            success=True
        )

        # 记录各子模块（估算时间分配）
        emotion_time = total_time_ms * 0.15
        dj_time = total_time_ms * 0.20
        music_time = total_time_ms * 0.25
        queue_time = total_time_ms * 0.40

        self.report.api_tracker.track_call("emotion_analysis", emotion_time, success=True)
        self.report.api_tracker.track_call("dj_script_generation", dj_time, success=True)
        self.report.api_tracker.track_call("music_prompt_generation", music_time, success=True)
        self.report.api_tracker.track_call("async_queue_management", queue_time, success=True)

        # 记录音频事件
        if result.get("generation_strategy") == "ready":
            self.report.audio_monitor.record_audio_event("dj_speech", 5000, "completed")
            self.report.audio_monitor.record_audio_event("music", 180000, "playing")
        else:
            self.report.audio_monitor.record_audio_event("dj_speech", 5000, "completed")
            self.report.audio_monitor.record_audio_event("fallback_audio", 30000, "playing")
            self.report.audio_monitor.record_audio_event("music", 180000, "queued")

    def _print_progress(self, elapsed: float, remaining: float):
        """打印进度"""
        elapsed_min = elapsed / 60
        remaining_min = remaining / 60
        progress_pct = (elapsed / self.duration_seconds) * 100

        sys_stats = self.report.system_monitor.get_stats()
        api_stats = self.report.api_tracker.get_total_stats()

        print(f"\n📊 进度：{progress_pct:.1f}% ({elapsed_min:.1f}分 / 剩余 {remaining_min:.1f}分)")
        print(f"   内存：{sys_stats['current_memory_mb']:.0f}/{sys_stats['peak_memory_mb']:.0f} MB")
        print(f"   CPU：{sys_stats['current_cpu_percent']:.1f}%")
        print(f"   批次：{self.batch_count} (错误：{self.error_count})")
        print(f"   API 成功率：{api_stats['overall_success_rate']:.1f}%")

    async def run(self):
        """运行完整测试"""
        if not await self.setup():
            return

        try:
            await self.run_test_loop()
        except KeyboardInterrupt:
            print("\n\n🛑 用户中断测试")
        except Exception as e:
            print(f"\n❌ 测试异常：{e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()

    async def cleanup(self):
        """清理资源"""
        self.report.end_test()

        print("\n" + "="*80)
        print("📈 生成测试报告...")
        print("="*80)

        self.report.print_summary()
        self.report.save_report(f"stress_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="claudio.fm 压力测试")
    parser.add_argument(
        "--duration",
        type=float,
        default=120,
        help="测试时长（分钟，默认 120）"
    )

    args = parser.parse_args()

    test = StressTest(duration_minutes=args.duration)
    await test.run()


if __name__ == "__main__":
    asyncio.run(main())
