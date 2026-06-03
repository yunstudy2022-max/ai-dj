"""
Task 2.4 — 音乐生成提示词构建引擎
为 Suno API 生成优化的音乐参数和提示词

使用方式：
    python music-generator.py --mood melancholic --tempo slow
"""

import os
import json
import hashlib
from typing import Dict, List, Tuple
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class MusicPromptGenerator:
    """音乐生成提示词构建器"""

    # 情绪到音乐特征的映射表
    MOOD_TO_MUSIC = {
        "melancholic": {
            "genres": ["Lo-Fi hip hop", "Ambient", "Sad piano"],
            "instruments": ["melancholic piano", "strings", "slow drums"],
            "mood_descriptors": ["introspective", "melancholic", "deep"],
            "bpm": "60-80",
            "tempo": "slow",
            "energy": "low",
            "vocal": "no vocals"
        },
        "energetic": {
            "genres": ["Jazzhop", "Upbeat Lo-Fi", "House"],
            "instruments": ["upbeat drums", "jazz piano", "bass"],
            "mood_descriptors": ["uplifting", "energetic", "warm"],
            "bpm": "100-120",
            "tempo": "moderate",
            "energy": "high",
            "vocal": "no vocals"
        },
        "neutral": {
            "genres": ["Lo-Fi hip hop", "Chillhop", "Background music"],
            "instruments": ["smooth drums", "warm piano", "subtle bass"],
            "mood_descriptors": ["calm", "peaceful", "balanced"],
            "bpm": "85-95",
            "tempo": "moderate",
            "energy": "medium",
            "vocal": "no vocals"
        },
        "introspective": {
            "genres": ["Ambient", "Drone", "Minimal"],
            "instruments": ["sparse piano", "ambient pads", "field recordings"],
            "mood_descriptors": ["reflective", "thoughtful", "meditative"],
            "bpm": "40-70",
            "tempo": "very slow",
            "energy": "very low",
            "vocal": "optional breathy vocals"
        },
        "mixed": {
            "genres": ["Lo-Fi hip hop", "Chillhop"],
            "instruments": ["balanced drums", "piano", "subtle strings"],
            "mood_descriptors": ["dynamic", "evolving", "textured"],
            "bpm": "85-100",
            "tempo": "moderate",
            "energy": "medium",
            "vocal": "no vocals"
        }
    }

    # 时段特定的音乐微调
    TIME_PERIOD_TWEAKS = {
        "evening": {  # 18:00-21:00
            "energy_boost": 1.1,
            "warmth_factor": "bright, inviting",
            "extra_elements": "vinyl crackle, warm compression"
        },
        "midnight": {  # 21:00-00:00
            "energy_boost": 0.9,
            "warmth_factor": "sultry, intimate",
            "extra_elements": "subtle saxophone, bar ambience"
        },
        "late_night": {  # 00:00-03:00
            "energy_boost": 0.7,
            "warmth_factor": "fragile, vulnerable",
            "extra_elements": "sparse piano, silence gaps, breathing sounds"
        }
    }

    def __init__(self, api_key: str = None, cache_dir: str = None):
        """
        初始化音乐生成器

        Args:
            api_key: Suno API 密钥
            cache_dir: 缓存目录路径
        """
        self.api_key = api_key or os.getenv("SUNO_API_KEY")
        if not self.api_key:
            raise ValueError("SUNO_API_KEY not found in environment")

        self.cache_dir = cache_dir or "music_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        # 加载缓存
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """加载音乐生成缓存"""
        cache_file = os.path.join(self.cache_dir, "music_cache.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """保存音乐生成缓存"""
        cache_file = os.path.join(self.cache_dir, "music_cache.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def generate_prompt(
        self,
        mood: str,
        time_period: str = None,
        keywords: List[str] = None,
        custom_style: str = None
    ) -> Dict:
        """
        生成 Suno API 的音乐提示词

        Args:
            mood: 情绪类型 (melancholic/energetic/neutral/introspective/mixed)
            time_period: 时段 (evening/midnight/late_night)
            keywords: 额外的关键词列表
            custom_style: 自定义音乐风格

        Returns:
            {
                "prompt": "完整的音乐生成提示词",
                "style": "主要风格",
                "bpm": "节奏",
                "cache_key": "缓存键"
            }
        """
        # 验证情绪
        if mood not in self.MOOD_TO_MUSIC:
            mood = "neutral"

        # 获取基础音乐特征
        base_music = self.MOOD_TO_MUSIC[mood].copy()

        # 应用时段微调
        if time_period and time_period in self.TIME_PERIOD_TWEAKS:
            tweaks = self.TIME_PERIOD_TWEAKS[time_period]
            base_music["warmth_factor"] = tweaks["warmth_factor"]
            base_music["extra_elements"] = tweaks["extra_elements"]

        # 构建提示词
        genre = base_music["genres"][0]
        instruments = ", ".join(base_music["instruments"][:3])
        mood_desc = ", ".join(base_music["mood_descriptors"])
        bpm = base_music["bpm"]
        warmth = base_music.get("warmth_factor", "")
        extra = base_music.get("extra_elements", "")

        prompt_parts = [
            genre,
            instruments,
            mood_desc,
            warmth,
            bpm,
            base_music["vocal"],
            extra
        ]

        # 添加自定义关键词
        if keywords:
            prompt_parts.extend(keywords)

        # 添加自定义风格
        if custom_style:
            prompt_parts.insert(1, custom_style)

        full_prompt = ", ".join([p for p in prompt_parts if p])

        # 生成缓存键
        cache_key = self._generate_cache_key(mood, time_period, keywords)

        return {
            "prompt": full_prompt,
            "style": genre,
            "bpm": bpm,
            "mood": mood,
            "time_period": time_period or "default",
            "cache_key": cache_key,
            "is_cached": cache_key in self.cache
        }

    def _generate_cache_key(
        self,
        mood: str,
        time_period: str = None,
        keywords: List[str] = None
    ) -> str:
        """
        生成唯一的缓存键

        Args:
            mood: 情绪
            time_period: 时段
            keywords: 关键词列表

        Returns:
            缓存键
        """
        key_data = f"{mood}:{time_period or 'default'}:{','.join(sorted(keywords or []))}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]

    def get_cached_music(self, cache_key: str) -> Dict:
        """
        从缓存中获取音乐 ID

        Args:
            cache_key: 缓存键

        Returns:
            缓存的音乐数据或 None
        """
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            cached["retrieved_at"] = datetime.now().isoformat()
            return cached
        return None

    def save_generated_music(
        self,
        cache_key: str,
        music_id: str,
        prompt: str,
        metadata: Dict = None
    ):
        """
        保存生成的音乐到缓存

        Args:
            cache_key: 缓存键
            music_id: Suno 返回的音乐 ID
            prompt: 使用的提示词
            metadata: 额外的元数据
        """
        self.cache[cache_key] = {
            "music_id": music_id,
            "prompt": prompt,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self._save_cache()

    def batch_generate_prompts(
        self,
        mood_analysis: Dict,
        time_period: str = None
    ) -> List[Dict]:
        """
        为不同的情绪关键词生成多个提示词

        Args:
            mood_analysis: 情绪分析结果
            time_period: 时段

        Returns:
            生成的提示词列表
        """
        mood = mood_analysis.get("overall_mood", "neutral")
        keywords = mood_analysis.get("keywords", [])

        prompts = []

        # 主提示词（基于整体气氛）
        main_prompt = self.generate_prompt(
            mood=mood,
            time_period=time_period,
            keywords=keywords[:2]
        )
        prompts.append(main_prompt)

        # 备选提示词（变化的风格）
        if mood != "mixed":
            variation_mood = "neutral" if mood != "neutral" else "energetic"
            variation_prompt = self.generate_prompt(
                mood=variation_mood,
                time_period=time_period,
                keywords=keywords[2:4] if len(keywords) > 2 else []
            )
            prompts.append(variation_prompt)

        return prompts

    def get_music_parameters(self, mood: str) -> Dict:
        """
        获取特定情绪的音乐参数

        Args:
            mood: 情绪类型

        Returns:
            音乐参数字典
        """
        if mood not in self.MOOD_TO_MUSIC:
            mood = "neutral"

        music = self.MOOD_TO_MUSIC[mood]
        return {
            "genres": music["genres"],
            "instruments": music["instruments"],
            "bpm": music["bpm"],
            "tempo": music["tempo"],
            "energy": music["energy"]
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Music Prompt Generator")
    parser.add_argument("--mood", default="melancholic", help="Mood type")
    parser.add_argument("--time", help="Time period (evening/midnight/late_night)")
    parser.add_argument("--keywords", nargs="+", help="Custom keywords")
    parser.add_argument("--style", help="Custom style")

    args = parser.parse_args()

    try:
        generator = MusicPromptGenerator()

        result = generator.generate_prompt(
            mood=args.mood,
            time_period=args.time,
            keywords=args.keywords,
            custom_style=args.style
        )

        print("\n" + "="*60)
        print(f"【{result['mood'].upper()}】")
        print("="*60)
        print(f"\n🎵 提示词：\n{result['prompt']}")
        print(f"\n📊 参数：")
        print(f"  • 风格：{result['style']}")
        print(f"  • BPM：{result['bpm']}")
        print(f"  • 缓存键：{result['cache_key']}")
        print(f"  • 已缓存：{'✅ 是' if result['is_cached'] else '❌ 否'}")
        print("\n" + "="*60)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
