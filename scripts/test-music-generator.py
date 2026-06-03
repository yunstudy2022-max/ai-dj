"""
Task 2.4 音乐生成测试脚本
"""

import json
import sys
sys.path.append(".")

from music_generator import MusicPromptGenerator

def test_prompt_generation():
    """测试提示词生成"""
    print("\n" + "="*60)
    print("TEST 1: 不同情绪的音乐提示词")
    print("="*60)

    generator = MusicPromptGenerator()

    test_cases = [
        ("melancholic", "late_night", ["work", "tired"]),
        ("energetic", "evening", ["happy", "uplifting"]),
        ("introspective", "midnight", ["lonely", "thoughtful"]),
        ("neutral", None, [])
    ]

    for mood, time_period, keywords in test_cases:
        result = generator.generate_prompt(
            mood=mood,
            time_period=time_period,
            keywords=keywords
        )

        print(f"\n【{mood.upper()}】 {time_period or '(default)'}")
        print(f"提示词：{result['prompt']}")
        print(f"BPM：{result['bpm']}")
        print(f"缓存键：{result['cache_key']}")


def test_time_period_variation():
    """测试时段对音乐的影响"""
    print("\n" + "="*60)
    print("TEST 2: 同一情绪在不同时段的变化")
    print("="*60)

    generator = MusicPromptGenerator()
    mood = "melancholic"
    keywords = ["tired", "work"]

    times = ["evening", "midnight", "late_night"]

    for time_period in times:
        result = generator.generate_prompt(
            mood=mood,
            time_period=time_period,
            keywords=keywords
        )
        print(f"\n{time_period}:")
        print(f"  {result['prompt'][:80]}...")


def test_batch_generation():
    """测试批量生成"""
    print("\n" + "="*60)
    print("TEST 3: 批量生成提示词（聊天室气氛）")
    print("="*60)

    generator = MusicPromptGenerator()

    mood_analysis = {
        "overall_mood": "melancholic",
        "dominant_emotion": "tired",
        "keywords": ["work", "sleep", "lonely", "coffee", "night"]
    }

    prompts = generator.batch_generate_prompts(
        mood_analysis=mood_analysis,
        time_period="late_night"
    )

    for i, prompt in enumerate(prompts, 1):
        print(f"\n选项 {i}：")
        print(f"  提示词：{prompt['prompt'][:100]}...")
        print(f"  缓存：{'✅ 已有' if prompt['is_cached'] else '❌ 新建'}")


def test_music_parameters():
    """测试音乐参数提取"""
    print("\n" + "="*60)
    print("TEST 4: 情绪到音乐参数的映射")
    print("="*60)

    generator = MusicPromptGenerator()

    moods = ["melancholic", "energetic", "introspective"]

    for mood in moods:
        params = generator.get_music_parameters(mood)
        print(f"\n【{mood}】")
        print(f"  风格：{', '.join(params['genres'][:2])}")
        print(f"  乐器：{', '.join(params['instruments'][:2])}")
        print(f"  BPM：{params['bpm']}")
        print(f"  能量：{params['energy']}")


if __name__ == "__main__":
    try:
        test_prompt_generation()
        test_time_period_variation()
        test_batch_generation()
        test_music_parameters()
        print("\n✅ 所有测试完成")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
