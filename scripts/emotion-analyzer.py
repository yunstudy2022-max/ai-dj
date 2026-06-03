"""
情绪分析引擎
使用 DeepSeek-V4 API 分析留言情绪

使用方式：
    python emotion-analyzer.py --text "今晚加班好累"

依赖：
    pip install requests python-dotenv
"""

import os
import json
import requests
from typing import List, Dict
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class EmotionAnalyzer:
    """基于 DeepSeek-V4 的情绪分析器"""

    def __init__(self, api_key: str = None):
        """
        初始化情绪分析器

        Args:
            api_key: DeepSeek API 密钥，默认从 .env 读取
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")

        self.api_url = "https://api.deepseek.com/chat/completions"
        self.model = "deepseek-chat"

    def analyze_message(self, text: str) -> Dict:
        """
        分析单条留言的情绪

        Args:
            text: 留言文本

        Returns:
            {
                "dominant_emotion": "sad",
                "confidence": 0.85,
                "keywords": ["tired", "work"],
                "mood_category": "melancholic"
            }
        """
        prompt = f"""分析以下留言的情绪，用中文和英文标注。

留言: {text}

请按以下 JSON 格式返回（仅返回 JSON，无其他文本）：
{{
    "dominant_emotion": "sad/happy/neutral/introspective",
    "confidence": 0.0-1.0,
    "keywords": ["keyword1", "keyword2", ...],
    "mood_category": "melancholic/energetic/neutral/reflective"
}}"""

        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 200
            }
        )

        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code} - {response.text}")

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()

        # 提取 JSON
        try:
            emotion_data = json.loads(content)
        except json.JSONDecodeError:
            # 如果 API 返回的不是纯 JSON，尝试提取 JSON 部分
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                emotion_data = json.loads(content[start:end])
            else:
                raise ValueError(f"Failed to parse emotion response: {content}")

        return emotion_data

    def analyze_batch(self, messages: List[str]) -> Dict:
        """
        分析多条留言的整体情绪

        Args:
            messages: 留言文本列表（最近 12 条）

        Returns:
            {
                "overall_mood": "melancholic",
                "dominant_emotion": "tired",
                "confidence": 0.87,
                "keywords": ["work", "sleep", "lonely"],
                "message_breakdown": [emotion_data1, emotion_data2, ...]
            }
        """
        # 分析每条消息
        individual_analyses = []
        for msg in messages[:12]:  # 最多12条
            try:
                analysis = self.analyze_message(msg)
                individual_analyses.append(analysis)
            except Exception as e:
                print(f"Error analyzing message '{msg}': {e}")
                continue

        if not individual_analyses:
            return {
                "overall_mood": "unknown",
                "dominant_emotion": "neutral",
                "confidence": 0.0,
                "keywords": [],
                "message_breakdown": []
            }

        # 综合分析
        messages_text = "\n".join([f"- {msg}" for msg in messages[:12]])
        batch_prompt = f"""分析以下 12 条直播聊天室留言的整体气氛。

留言列表：
{messages_text}

请按以下 JSON 格式返回（仅返回 JSON，无其他文本）：
{{
    "overall_mood": "melancholic/energetic/neutral/mixed",
    "dominant_emotion": "sad/happy/neutral/tired/excited/introspective",
    "confidence": 0.0-1.0,
    "keywords": ["keyword1", "keyword2", "keyword3", ...],
    "summary": "用一句话总结聊天室气氛"
}}"""

        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": batch_prompt}],
                "temperature": 0.7,
                "max_tokens": 300
            }
        )

        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code}")

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()

        try:
            batch_analysis = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}") + 1
            batch_analysis = json.loads(content[start:end]) if start >= 0 and end > start else {}

        batch_analysis["message_breakdown"] = individual_analyses
        batch_analysis["analyzed_at"] = datetime.now().isoformat()

        return batch_analysis


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Emotion Analyzer")
    parser.add_argument("--text", help="Single message to analyze")
    parser.add_argument("--batch", action="store_true", help="Analyze multiple messages")

    args = parser.parse_args()

    try:
        analyzer = EmotionAnalyzer()

        if args.text:
            print("Analyzing single message...")
            result = analyzer.analyze_message(args.text)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.batch:
            test_messages = [
                "今晚加班好累",
                "听你的电台心情好多了",
                "半夜3点还醒着",
                "工作压力好大",
                "谢谢陪伴"
            ]
            print("Analyzing batch of messages...")
            result = analyzer.analyze_batch(test_messages)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("Usage: python emotion-analyzer.py --text '留言内容' or --batch")
    except Exception as e:
        print(f"Error: {e}")
