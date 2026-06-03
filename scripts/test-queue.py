"""
Task 2.5 异步队列管理测试
"""

import asyncio
import json
import sys
sys.path.append(".")

from queue_manager import (
    AudioQueue, AudioItemStatus, AsyncMusicGenerator,
    FallbackAudioLibrary, SystemOrchestrator
)


async def test_basic_queue():
    """测试基础队列功能"""
    print("\n" + "="*60)
    print("TEST 1: 基础队列操作")
    print("="*60)

    queue = AudioQueue(max_queue_size=20)

    # 添加项目
    dj_id = queue.add_item(
        audio_type="dj_speech",
        content={"text": "有时候，靜靜聽著就夠了。"},
        duration=5
    )
    print(f"\n✅ 添加 DJ 讲话：{dj_id}")

    music_id = queue.add_item(
        audio_type="suno_music",
        content={"prompt": "Lo-Fi hip hop..."},
        duration=180
    )
    print(f"✅ 添加音乐生成：{music_id}")

    # 更新状态
    queue.update_status(dj_id, AudioItemStatus.READY)
    print(f"✅ DJ 状态更新为 READY")

    queue.update_status(music_id, AudioItemStatus.GENERATING)
    print(f"✅ 音乐状态更新为 GENERATING")

    # 查看队列
    print(f"\n📋 队列内容：")
    for item in queue.peek_queue():
        print(f"  [{item['id']}] {item['type']}: {item['status']}")


async def test_fallback_selection():
    """测试过渡音乐选择"""
    print("\n" + "="*60)
    print("TEST 2: 过渡音乐智能选择")
    print("="*60)

    moods = ["melancholic", "energetic", "introspective"]

    for mood in moods:
        fallback = FallbackAudioLibrary.get_fallback_for_mood(mood, duration=30)
        audio = FallbackAudioLibrary.FALLBACK_AUDIOS[fallback]
        print(f"\n【{mood}】→ {audio['name']} ({audio['duration']}s)")


async def test_async_generation():
    """测试异步音乐生成（带超时）"""
    print("\n" + "="*60)
    print("TEST 3: 异步音乐生成（模拟 Suno API）")
    print("="*60)

    queue = AudioQueue()
    async_gen = AsyncMusicGenerator(queue)

    item_id = queue.add_item(
        audio_type="suno_music",
        content={"prompt": "Lo-Fi hip hop, melancholic piano"},
        duration=None
    )

    print(f"\n⏳ 启动异步音乐生成（item: {item_id}）")
    print(f"   DJ 讲话时长：10s")
    print(f"   等待超时：15s")

    result = await async_gen.generate_with_fallback(
        item_id=item_id,
        prompt="Lo-Fi hip hop, melancholic piano, vinyl crackle",
        mood="melancholic",
        dj_speech_duration=10
    )

    print(f"\n✅ 生成完成")
    print(f"   策略：{result['status']}")
    print(f"   时间线：")
    for key, value in result.get("timeline", {}).items():
        print(f"     • {key}: {value}")


async def test_full_orchestration():
    """测试完整的系统编排"""
    print("\n" + "="*60)
    print("TEST 4: 完整系统编排（聊天 → 情绪 → DJ → 音乐 → 队列）")
    print("="*60)

    orchestrator = SystemOrchestrator()

    # 模拟来自 YouTube 聊天的数据
    messages = ["今晚加班好累", "压力太大了", "需要陪伴"]
    mood_analysis = {
        "overall_mood": "melancholic",
        "dominant_emotion": "tired",
        "keywords": ["work", "pressure", "tired"],
        "confidence": 0.85
    }
    dj_script = "有时候，靜靜聽著就夠了。看你们加班这么辛苦，这首曲子就献给今晚还醒著的你。"
    music_prompt = "Lo-Fi hip hop, melancholic piano, vinyl crackle, slow drums, 68 bpm"

    print(f"\n📨 接收聊天消息：{len(messages)} 条")
    print(f"💭 情绪分析结果：{mood_analysis['overall_mood']}")
    print(f"📻 DJ 台词：{dj_script[:40]}...")
    print(f"🎵 音乐提示词：{music_prompt[:40]}...")

    result = await orchestrator.process_chat_batch(
        messages, mood_analysis, dj_script, music_prompt
    )

    print(f"\n✅ 处理完成")
    print(f"   生成策略：{result['generation_strategy']}")
    print(f"\n⏱️  时间线：")
    for key, value in result['timeline'].items():
        print(f"   • {key}: {value}")

    print(f"\n📋 当前队列：")
    for item in result['queue_status']:
        print(f"   [{item['id']}] {item['type']:20} → {item['status']}")


async def test_callback_system():
    """测试回调系统（WebSocket 推送模拟）"""
    print("\n" + "="*60)
    print("TEST 5: 回调系统（WebSocket 推送模拟）")
    print("="*60)

    queue = AudioQueue()

    # 注册回调
    def on_status_changed(data):
        print(f"   🔔 [推送] 项目 {data['item_id']} 状态变更："
              f" {data['old_status']} → {data['new_status']}")

    queue.register_callback("status_changed", on_status_changed)

    # 执行操作
    item_id = queue.add_item(
        audio_type="dj_speech",
        content={"text": "test"},
        duration=5
    )

    print(f"\n状态变更操作（会触发 WebSocket 推送）：")
    queue.update_status(item_id, AudioItemStatus.READY)
    queue.update_status(item_id, AudioItemStatus.PLAYING)
    queue.update_status(item_id, AudioItemStatus.COMPLETED)


async def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("Task 2.5 — 异步处理队列完整测试")
    print("="*80)

    await test_basic_queue()
    await test_fallback_selection()
    await test_async_generation()
    await test_full_orchestration()
    await test_callback_system()

    print("\n" + "="*80)
    print("✅ 所有测试完成")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
