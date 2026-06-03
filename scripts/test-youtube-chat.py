"""
YouTube Chat Fetcher 测试脚本

测试模式：
  1. 环境检查（无需 API Key）
  2. API 连接测试（需要 API Key）
  3. 与 integration-engine 的联调演示

使用方式：
  python test-youtube-chat.py              # 环境检查
  python test-youtube-chat.py --video-id VIDEO_ID   # 完整测试
"""

import os
import sys
import asyncio
import json
from datetime import datetime

# 路径设置（从 scripts/ 运行）
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


# ---------------------------------------------------------------
# Test 1: 环境检查
# ---------------------------------------------------------------

def test_environment():
    print("\n" + "="*60)
    print("Test 1: 环境检查")
    print("="*60)

    checks = {
        "YOUTUBE_API_KEY": bool(os.getenv("YOUTUBE_API_KEY")),
        "google-api-python-client": False,
        "python-dotenv": False,
    }

    try:
        from googleapiclient.discovery import build
        checks["google-api-python-client"] = True
    except ImportError:
        pass

    try:
        import dotenv
        checks["python-dotenv"] = True
    except ImportError:
        pass

    all_pass = True
    for name, ok in checks.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")
        if not ok:
            all_pass = False

    if not checks["google-api-python-client"]:
        print("\n  → 安装依赖：pip install google-api-python-client python-dotenv")

    if not checks["YOUTUBE_API_KEY"]:
        print("\n  → 在 .env 中填入：YOUTUBE_API_KEY=你的Key")

    return all_pass


# ---------------------------------------------------------------
# Test 2: API 连接（需要 Key + 直播中的视频）
# ---------------------------------------------------------------

def test_api_connection(video_id: str):
    print("\n" + "="*60)
    print(f"Test 2: API 连接测试（视频 {video_id}）")
    print("="*60)

    try:
        from youtube_chat_fetcher import YouTubeChatFetcher
        fetcher = YouTubeChatFetcher()
        print("  ✅ YouTubeChatFetcher 初始化成功")

        # 取得 liveChatId
        print("  → 尝试取得 liveChatId...")
        chat_id = fetcher.get_live_chat_id(video_id)
        print(f"  ✅ liveChatId: {chat_id[:30]}...")

        # 单次拉取
        print("  → 抓取最新留言...")
        messages = fetcher.fetch_live_chat(video_id, limit=10)
        print(f"  ✅ 取得 {len(messages)} 条留言")

        for i, m in enumerate(messages[:5], 1):
            print(f"    [{i}] {m['author']}: {m['text'][:40]}")
        if len(messages) > 5:
            print(f"    ... 还有 {len(messages)-5} 条")

        return messages

    except ValueError as e:
        print(f"  ❌ {e}")
        return []
    except Exception as e:
        print(f"  ❌ 意外错误：{e}")
        return []


# ---------------------------------------------------------------
# Test 3: 与 integration-engine 联调
# ---------------------------------------------------------------

async def test_integration(video_id: str):
    print("\n" + "="*60)
    print("Test 3: 与 integration-engine 联调")
    print("="*60)

    try:
        from youtube_chat_fetcher import YouTubeChatFetcher
        from integration_engine import ClaudioFMEngine

        fetcher = YouTubeChatFetcher()
        engine = ClaudioFMEngine()

        # 抓取留言（纯文字）
        print("  → 抓取 YouTube 留言...")
        texts = fetcher.fetch_text_only(video_id, limit=12)
        if not texts:
            print("  ⚠️  没有留言，跳过联调测试")
            return

        print(f"  ✅ 取得 {len(texts)} 条文字留言")

        # 传给 integration engine
        print("  → 传入 integration engine 处理...")
        result = await engine.process_youtube_chat_batch(
            messages=texts,
            time_period=_get_time_period()
        )

        if result["status"] == "success":
            print(f"  ✅ 联调成功！")
            print(f"     情绪：{result['emotion_analysis'].get('dominant_emotion')}")
            print(f"     DJ台词：{result['dj_script'][:50]}...")
        else:
            print(f"  ❌ 联调失败：{result.get('error')}")

    except Exception as e:
        print(f"  ❌ {e}")


# ---------------------------------------------------------------
# Test 4: 短时轮询演示（30 秒，不需要跑完整直播）
# ---------------------------------------------------------------

async def test_poll_demo(video_id: str, seconds: int = 30):
    print("\n" + "="*60)
    print(f"Test 4: 轮询模式演示（{seconds} 秒）")
    print("="*60)

    try:
        from youtube_chat_fetcher import YouTubeChatFetcher

        fetcher = YouTubeChatFetcher()
        received_batches = []

        def on_batch(messages):
            received_batches.append(messages)
            print(f"  📨 批次 #{len(received_batches)}：{len(messages)} 条留言")
            for m in messages[:3]:
                print(f"     {m['author']}: {m['text'][:30]}")

        # 设置超时
        try:
            await asyncio.wait_for(
                fetcher.poll_forever(
                    video_id=video_id,
                    on_batch=on_batch,
                    batch_size=5
                ),
                timeout=seconds
            )
        except asyncio.TimeoutError:
            print(f"\n  ✅ {seconds} 秒演示完成，共收到 {len(received_batches)} 个批次")

    except Exception as e:
        print(f"  ❌ {e}")


# ---------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------

def _get_time_period() -> str:
    hour = datetime.now().hour
    if 18 <= hour < 21:
        return "evening"
    elif 21 <= hour or hour < 0:
        return "midnight"
    return "late_night"


def _fix_module_name():
    """处理文件名含连字符的导入问题，必须先全部注册再执行，否则循环 import 会失败"""
    import importlib.util, pathlib
    script_dir = pathlib.Path(__file__).parent

    # 所有连字符模块映射（顺序无关，先全部注册壳）
    mappings = [
        ("youtube-chat-fetcher.py", "youtube_chat_fetcher"),
        ("emotion-analyzer.py",     "emotion_analyzer"),
        ("dj-script-generator.py",  "dj_script_generator"),
        ("music-generator.py",      "music_generator"),
        ("queue-manager.py",        "queue_manager"),
        ("obs-controller.py",       "obs_controller"),
        ("integration-engine.py",   "integration_engine"),
    ]

    # 第一步：建立所有模块的空壳并注册到 sys.modules
    specs = {}
    for src_name, mod_name in mappings:
        src = script_dir / src_name
        if src.exists() and mod_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(mod_name, src)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            specs[mod_name] = (spec, mod)

    # 第二步：依序执行各模块（此时 sys.modules 已有所有壳，import 不会失败）
    for mod_name, (spec, mod) in specs.items():
        spec.loader.exec_module(mod)


# ---------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YouTube Chat Fetcher 测试")
    parser.add_argument("--video-id", help="YouTube 直播视频 ID")
    parser.add_argument(
        "--poll", action="store_true",
        help="包含轮询模式演示（30 秒）"
    )
    args = parser.parse_args()

    _fix_module_name()

    # Test 1 总是跑
    env_ok = test_environment()

    if args.video_id:
        if not env_ok:
            print("\n⚠️  环境检查未通过，跳过 API 测试")
        else:
            messages = test_api_connection(args.video_id)

            if messages:
                asyncio.run(test_integration(args.video_id))

                if args.poll:
                    asyncio.run(test_poll_demo(args.video_id, seconds=30))

    else:
        print("\n提示：传入 --video-id 进行完整 API 测试")
        print("  例：python test-youtube-chat.py --video-id dQw4w9WgXcQ")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
