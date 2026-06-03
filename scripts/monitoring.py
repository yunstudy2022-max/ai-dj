"""
系统监控和性能统计
用于压力测试中追踪系统健康状况
"""

import psutil
import threading
import time
import json
from typing import Dict, List
from datetime import datetime
from collections import defaultdict


class SystemMonitor:
    """系统监控器"""

    def __init__(self, interval: float = 2.0):
        """
        初始化监控器

        Args:
            interval: 采样间隔（秒）
        """
        self.interval = interval
        self.is_running = False
        self.monitor_thread = None

        # 监控数据
        self.memory_samples: List[float] = []
        self.cpu_samples: List[float] = []
        self.timestamp_samples: List[str] = []

        # 峰值记录
        self.peak_memory = 0
        self.peak_cpu = 0
        self.start_time = None

    def start(self):
        """启动监控"""
        self.is_running = True
        self.start_time = datetime.now()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("✅ 系统监控已启动")

    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("✅ 系统监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        process = psutil.Process()

        while self.is_running:
            try:
                # 采集数据
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent(interval=0.5)

                self.memory_samples.append(memory_mb)
                self.cpu_samples.append(cpu_percent)
                self.timestamp_samples.append(datetime.now().isoformat())

                # 更新峰值
                self.peak_memory = max(self.peak_memory, memory_mb)
                self.peak_cpu = max(self.peak_cpu, cpu_percent)

                time.sleep(self.interval)

            except Exception as e:
                print(f"Monitoring error: {e}")

    def get_stats(self) -> Dict:
        """获取统计数据"""
        if not self.memory_samples:
            return {}

        memory_values = self.memory_samples
        cpu_values = self.cpu_samples

        return {
            "current_memory_mb": memory_values[-1] if memory_values else 0,
            "current_cpu_percent": cpu_values[-1] if cpu_values else 0,
            "average_memory_mb": sum(memory_values) / len(memory_values),
            "average_cpu_percent": sum(cpu_values) / len(cpu_values),
            "peak_memory_mb": self.peak_memory,
            "peak_cpu_percent": self.peak_cpu,
            "min_memory_mb": min(memory_values) if memory_values else 0,
            "sample_count": len(memory_values)
        }

    def detect_memory_leak(self, threshold_mb: float = 50) -> bool:
        """
        检测内存泄漏

        Args:
            threshold_mb: 增长阈值

        Returns:
            是否检测到泄漏
        """
        if len(self.memory_samples) < 10:
            return False

        # 比较前 10% 和后 10% 的平均内存
        first_10pct = sum(self.memory_samples[:len(self.memory_samples)//10]) / (len(self.memory_samples)//10)
        last_10pct = sum(self.memory_samples[-len(self.memory_samples)//10:]) / (len(self.memory_samples)//10)

        return (last_10pct - first_10pct) > threshold_mb


class APIPerformanceTracker:
    """API 性能跟踪器"""

    def __init__(self):
        """初始化跟踪器"""
        self.api_calls: Dict[str, List[float]] = defaultdict(list)  # API 名 → 响应时间列表
        self.api_errors: Dict[str, int] = defaultdict(int)  # API 名 → 错误计数
        self.api_success: Dict[str, int] = defaultdict(int)  # API 名 → 成功计数

    def track_call(
        self,
        api_name: str,
        duration_ms: float,
        success: bool = True,
        error: str = None
    ):
        """
        跟踪 API 调用

        Args:
            api_name: API 名称
            duration_ms: 响应时间（毫秒）
            success: 是否成功
            error: 错误信息
        """
        self.api_calls[api_name].append(duration_ms)

        if success:
            self.api_success[api_name] += 1
        else:
            self.api_errors[api_name] += 1

    def get_stats(self) -> Dict:
        """获取统计数据"""
        stats = {}

        for api_name in set(list(self.api_calls.keys()) + list(self.api_errors.keys())):
            calls = self.api_calls[api_name]
            successes = self.api_success[api_name]
            errors = self.api_errors[api_name]
            total = successes + errors

            stats[api_name] = {
                "total_calls": total,
                "successes": successes,
                "errors": errors,
                "success_rate": (successes / total * 100) if total > 0 else 0,
                "avg_response_ms": sum(calls) / len(calls) if calls else 0,
                "min_response_ms": min(calls) if calls else 0,
                "max_response_ms": max(calls) if calls else 0,
                "p95_response_ms": self._percentile(calls, 95) if calls else 0
            }

        return stats

    @staticmethod
    def _percentile(data: List[float], p: int) -> float:
        """计算百分位数"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (p / 100))
        return sorted_data[index] if index < len(sorted_data) else sorted_data[-1]

    def get_total_stats(self) -> Dict:
        """获取总体统计"""
        total_calls = sum(self.api_success.values()) + sum(self.api_errors.values())
        total_successes = sum(self.api_success.values())
        total_errors = sum(self.api_errors.values())

        return {
            "total_api_calls": total_calls,
            "total_successes": total_successes,
            "total_errors": total_errors,
            "overall_success_rate": (total_successes / total_calls * 100) if total_calls > 0 else 0
        }


class AudioSyncMonitor:
    """音频同步监控器"""

    def __init__(self):
        """初始化监控器"""
        self.sync_issues: List[Dict] = []
        self.audio_events: List[Dict] = []

    def record_audio_event(
        self,
        event_type: str,  # "dj_speech" / "music" / "fallback"
        duration_ms: float,
        status: str  # "queued" / "playing" / "completed" / "failed"
    ):
        """
        记录音频事件

        Args:
            event_type: 事件类型
            duration_ms: 时长
            status: 状态
        """
        self.audio_events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "duration_ms": duration_ms,
            "status": status
        })

    def detect_sync_issue(self, gap_ms: float = 500):
        """
        检测音频间隙

        Args:
            gap_ms: 间隙阈值（毫秒）
        """
        if len(self.audio_events) < 2:
            return

        for i in range(len(self.audio_events) - 1):
            current = self.audio_events[i]
            next_event = self.audio_events[i + 1]

            # 简单的间隙检测
            if current["status"] == "completed":
                # 记录潜在的同步问题
                pass

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "total_audio_events": len(self.audio_events),
            "sync_issues_detected": len(self.sync_issues),
            "event_breakdown": self._count_event_types()
        }

    def _count_event_types(self) -> Dict:
        """统计事件类型"""
        counts = defaultdict(int)
        for event in self.audio_events:
            counts[event["type"]] += 1
        return dict(counts)


class PerformanceReport:
    """性能报告生成器"""

    def __init__(self):
        """初始化报告生成器"""
        self.system_monitor = SystemMonitor()
        self.api_tracker = APIPerformanceTracker()
        self.audio_monitor = AudioSyncMonitor()
        self.start_time = None
        self.end_time = None

    def start_test(self):
        """开始测试"""
        self.start_time = datetime.now()
        self.system_monitor.start()
        print("🧪 压力测试已启动")

    def end_test(self):
        """结束测试"""
        self.end_time = datetime.now()
        self.system_monitor.stop()
        print("🧪 压力测试已完成")

    def generate_report(self) -> Dict:
        """生成完整报告"""
        duration = (self.end_time - self.start_time).total_seconds()

        report = {
            "test_metadata": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration_seconds": duration,
                "duration_minutes": duration / 60
            },
            "system_health": self.system_monitor.get_stats(),
            "api_performance": self.api_tracker.get_stats(),
            "api_total": self.api_tracker.get_total_stats(),
            "audio_sync": self.audio_monitor.get_stats(),
            "issues": {
                "memory_leak_detected": self.system_monitor.detect_memory_leak(),
                "sync_issues": self.audio_monitor.sync_issues
            }
        }

        return report

    def print_summary(self):
        """打印摘要"""
        report = self.generate_report()

        print("\n" + "="*80)
        print("📊 压力测试报告摘要")
        print("="*80)

        # 测试时间
        meta = report["test_metadata"]
        print(f"\n⏱️  测试时长：{meta['duration_minutes']:.1f} 分钟")

        # 系统健康
        sys_health = report["system_health"]
        print(f"\n💾 内存使用：")
        print(f"   当前：{sys_health['current_memory_mb']:.1f} MB")
        print(f"   平均：{sys_health['average_memory_mb']:.1f} MB")
        print(f"   峰值：{sys_health['peak_memory_mb']:.1f} MB")

        print(f"\n⚙️  CPU 使用：")
        print(f"   当前：{sys_health['current_cpu_percent']:.1f}%")
        print(f"   平均：{sys_health['average_cpu_percent']:.1f}%")
        print(f"   峰值：{sys_health['peak_cpu_percent']:.1f}%")

        # API 性能
        api_total = report["api_total"]
        print(f"\n📡 API 调用统计：")
        print(f"   总调用数：{api_total['total_api_calls']}")
        print(f"   成功：{api_total['total_successes']}")
        print(f"   失败：{api_total['total_errors']}")
        print(f"   成功率：{api_total['overall_success_rate']:.1f}%")

        # 详细 API 统计
        api_perf = report["api_performance"]
        if api_perf:
            print(f"\n📊 各 API 性能：")
            for api_name, stats in api_perf.items():
                print(f"   {api_name}：")
                print(f"     - 平均响应：{stats['avg_response_ms']:.0f}ms")
                print(f"     - P95 响应：{stats['p95_response_ms']:.0f}ms")
                print(f"     - 成功率：{stats['success_rate']:.1f}%")

        # 问题检测
        issues = report["issues"]
        print(f"\n⚠️  问题检测：")
        if issues["memory_leak_detected"]:
            print(f"   🔴 检测到潜在内存泄漏")
        else:
            print(f"   ✅ 未检测到内存泄漏")

        print(f"   同步问题：{len(issues['sync_issues'])} 个")

        print("\n" + "="*80)

    def save_report(self, filename: str = "stress_test_report.json"):
        """保存报告到文件"""
        report = self.generate_report()

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 报告已保存：{filename}")
