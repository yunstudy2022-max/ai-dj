"""
Task 2.3 DJ 文案生成测试脚本
"""

import json
import sys
sys.path.append(".")

from dj_script_generator import DJScriptGenerator

def test_script_generation():
    """测试 DJ 文案生成"""
    print("\n" + "="*60)
    print("TEST 1: DJ 文案生成（三个时段）")
    print("="*60)

    generator = DJScriptGenerator()

    test_cases = [
        {
            "hour": 19,
            "mood": "neutral",
            "listener": "Yuki",
            "emotion": "tired",
            "keywords": ["work", "tired"]
        },
        {
            "hour": 22,
            "mood": "melancholic",
            "listener": "张三",
            "emotion": "sad",
            "keywords": ["lonely", "heartbreak"]
        },
        {
            "hour": 1,
            "mood": "introspective",
            "listener": "Alice",
            "emotion": "introspective",
            "keywords": ["insomnia", "thoughts"]
        }
    ]

    for test in test_cases:
        mood_analysis = {
            "overall_mood": test["mood"],
            "dominant_emotion": test["emotion"],
            "keywords": test["keywords"],
            "confidence": 0.85
        }

        try:
            result = generator.generate_script(
                mood_analysis=mood_analysis,
                listener_name=test["listener"]
            )

            print(f"\n⏰ 时间：{result['time_range']}【{result['persona']}】")
            print(f"💭 气氛：{result['mood']}")
            print(f"🎵 音乐：{result['music_suggestion']}")
            print(f"📻 台词：{result['script']}")
        except Exception as e:
            print(f"\n❌ 生成失败: {e}")


def test_persona_switching():
    """测试时段自动切换"""
    print("\n" + "="*60)
    print("TEST 2: 时段人设自动切换")
    print("="*60)

    generator = DJScriptGenerator()

    hours = [19, 22, 1]
    for hour in hours:
        persona = generator.get_persona_by_time(hour)
        print(f"\n🕐 {hour}:00 → 【{persona['name']}】")
        print(f"   语气：{persona['tone']}")
        print(f"   选曲：{persona['music_style']}")


if __name__ == "__main__":
    try:
        test_persona_switching()
        test_script_generation()
        print("\n✅ 所有测试完成")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
