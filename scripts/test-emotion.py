"""
Task 2.2 情绪分析测试脚本
验证 DeepSeek-V4 API 集成
"""

import json
import sys
sys.path.append(".")

from emotion_analyzer import EmotionAnalyzer

def test_single_message():
    """测试单条留言分析"""
    print("\n" + "="*60)
    print("TEST 1: 单条留言分析")
    print("="*60)

    analyzer = EmotionAnalyzer()
    test_cases = [
        "今晚加班好累，一点精神都没有",
        "听了你的电台心情好多了！",
        "半夜3点还醒着，睡不着",
        "工作太累了，想放弃"
    ]

    for text in test_cases:
        print(f"\n留言: {text}")
        result = analyzer.analyze_message(text)
        print(f"情绪: {result.get('dominant_emotion')}")
        print(f"信心度: {result.get('confidence')}")
        print(f"关键词: {', '.join(result.get('keywords', []))}")
        print(f"分类: {result.get('mood_category')}")


def test_batch_analysis():
    """测试批量留言分析"""
    print("\n" + "="*60)
    print("TEST 2: 批量留言分析（聊天室整体气氛）")
    print("="*60)

    analyzer = EmotionAnalyzer()
    batch_messages = [
        "今晚加班好累",
        "同感，压力太大了",
        "但听着电台舒服多了",
        "对，陪伴很重要",
        "有时候静静听就够了",
        "深夜的孤独需要这样的陪伴",
        "谢谢你们",
        "互相支撑吧",
        "明天继续加油",
        "感谢这个电台的存在"
    ]

    print(f"\n分析 {len(batch_messages)} 条留言...")
    result = analyzer.analyze_batch(batch_messages)

    print(f"\n整体气氛: {result.get('overall_mood')}")
    print(f"主导情绪: {result.get('dominant_emotion')}")
    print(f"信心度: {result.get('confidence')}")
    print(f"关键词: {', '.join(result.get('keywords', []))}")
    print(f"总结: {result.get('summary')}")

    print(f"\n各留言情绪分析:")
    for i, breakdown in enumerate(result.get('message_breakdown', [])[:5]):
        print(f"  留言 {i+1}: {breakdown.get('dominant_emotion')} (信心: {breakdown.get('confidence')})")


if __name__ == "__main__":
    try:
        test_single_message()
        test_batch_analysis()
        print("\n✅ 所有测试完成")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
