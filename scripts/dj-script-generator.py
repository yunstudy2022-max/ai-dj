"""
Task 2.3 — DJ 文案生成引擎
使用 Claude 3.5 Sonnet API，根据聊天室气氛生成温暖的 DJ 台词

使用方式：
    python dj-script-generator.py --mood melancholic --listener "Yuki"
"""

import os
import json
import random
import requests
from typing import Dict, List
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# 每次廣播隨機抽一個切入角度，讓 AJ 像真正的 DJ 從不同方向探索主題
SCRIPT_ANGLES = [
    "從一個個人的小記憶切入，帶出今晚的氛圍感受",
    "輕輕提出一個問題給聽眾，像在和他們輕聲對話",
    "從今晚的時間感出發，描述現在這個時刻才有的感覺",
    "說一個和主題有關的日常小觀察，可以很瑣碎",
    "用一個比喻或畫面來描述今晚的氛圍，讓聽眾產生畫面",
    "說一段像在自言自語的內心獨白，碎碎念式的真實",
    "從某個感官細節出發——氣味、溫度、窗外的聲音",
    "分享一個在深夜突然想起的畫面或場景，不需要結論",
    "輕輕提到某種情緒，不解釋，讓它自己說話",
    "從聽眾的角度出發，說出他們此刻可能正在想的事",
    "聊聊時間流逝的感覺，今晚能陪在這裡是什麼感受",
    "說一件最近讓自己有感的小事，和主題自然串連起來",
    "用一個反問句開場，然後慢慢自己回答",
    "描述一種只有在深夜才會有的特殊心境或狀態",
    "從音樂本身說起，讓正在播的聲音和今晚主題產生連結",
    "說一個假設情境：如果今晚的空氣會說話，它會說什麼",
    "聊一聊選擇留下來聽廣播的人，他們此刻需要什麼",
]


class DJScriptGenerator:
    """基于 Claude 3.5 Sonnet 的 DJ 文案生成器"""

    # 三个时段的人设定义
    PERSONAS = {
        "evening": {
            "time_range": "18:00-21:00",
            "name": "晚安下班了",
            "vibe": "温暖、卸下装备、过渡期放松",
            "tone": "活力充沛、充满陪伴感",
            "music_style": "Jazzhop（节奏稍快）",
            "topics": "今天的小事、晚餐、工作吐槽",
            "sample": "你好呀，下班的人们。让我们一起卸下今天的装备，慢慢放松。"
        },
        "midnight": {
            "time_range": "21:00-00:00",
            "name": "深夜吧檯",
            "vibe": "故事感、微醺、大人时间",
            "tone": "低沉、话不多但句句见血",
            "music_style": "Lofi + 萨克斯风 + 微弱底噪",
            "topics": "感情、迷茫、深刻回忆",
            "sample": "时间越晚，故事越深。今晚你有什么想说的吗？"
        },
        "late_night": {
            "time_range": "00:00-03:00",
            "name": "I人的时光",
            "vibe": "绝对独处、无压力陪伴",
            "tone": "轻声细语、极度内敛",
            "music_style": "Ambient 环境音 + 极慢鋼琴",
            "topics": "无意义呢喃、失眠状态",
            "sample": "有时候，靜靜聽著就夠了。我在这里。"
        }
    }

    def __init__(self, api_key: str = None):
        """
        初始化 DJ 文案生成器

        Args:
            api_key: Claude API 密钥，默认从 .env 读取
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")

        self.api_url = "https://api.deepseek.com/chat/completions"
        self.model = "deepseek-chat"

    def get_persona_by_time(self, hour: int = None) -> Dict:
        """
        根据时间返回对应的 DJ 人设

        Args:
            hour: 24小时制的小时数，默认当前时间

        Returns:
            人设字典
        """
        if hour is None:
            hour = datetime.now().hour

        if 18 <= hour < 21:
            return self.PERSONAS["evening"]
        elif 21 <= hour < 24:
            return self.PERSONAS["midnight"]
        else:  # 0 <= hour < 3 or 3 <= hour < 18
            if 0 <= hour < 3:
                return self.PERSONAS["late_night"]
            else:
                # 白天（03:00-18:00）使用晚安人设作为备用
                return self.PERSONAS["evening"]

    def generate_script(
        self,
        mood_analysis: Dict,
        listener_name: str = None,
        custom_message: str = None,
        theme: str = "",
        script_history: List[str] = None
    ) -> Dict:
        """
        生成 DJ 文案

        Args:
            mood_analysis: 情绪分析结果（来自 emotion-analyzer.py）
            listener_name: 听众名字（用于个性化）
            custom_message: 自定义消息内容

        Returns:
            {
                "script": "有时候，靜靜聽著就夠了。Yuki，看你加班这么辛苦...",
                "persona": "I人的时光",
                "mood": "melancholic",
                "music_suggestion": "Ambient钢琴"
            }
        """
        persona = self.get_persona_by_time()
        mood = mood_analysis.get("overall_mood", "neutral")
        keywords = mood_analysis.get("keywords", [])

        # 构建 Prompt
        prompt = f"""你是一个深夜电台 DJ，名叫 AJ（我是你的朋友 - AJ）。你的角色设定如下：

【时段人设】
名字：{persona['name']}
时间：{persona['time_range']}
气质：{persona['vibe']}
语气：{persona['tone']}
选曲风格：{persona['music_style']}
话题焦点：{persona['topics']}

【当前聊天室气氛】
整体气氛：{mood}
主导情绪：{mood_analysis.get('dominant_emotion')}
关键词：{', '.join(keywords)}
"""

        if theme:
            prompt += f"\n【今晚節目主題】\n{theme}\n讓這段台詞自然扣回今晚的主題，不要生硬。"

        prompt += f"\n【這段台詞的切入角度】\n{random.choice(SCRIPT_ANGLES)}\n用這個角度說話，給聽眾新鮮感。"

        if script_history:
            history_text = "\n".join(f"— {s}" for s in script_history[-3:])
            prompt += f"\n【你剛才說過的話（請自然接續，不要重複）】\n{history_text}"

        if listener_name:
            prompt += f"\n【特定听众】\n名字：{listener_name}\n请个性化提及这位听众的名字。"

        if custom_message:
            prompt += f"\n【背景信息】\n{custom_message}"

        prompt += f"""

【任务】
根据上述背景，生成一段 60-90 字的温暖 DJ 台词。要求：
1. 符合时段人设的语气和气质
2. 像真正的深夜電台 DJ 在說話——有起伏、有停頓感、有畫面
3. 回应当前聊天室的整体气氛，自然承接上一段話的氛圍
4. 傳達溫暖、陪伴的感受，但不要說教或過度雞湯
5. 返回纯文本，不要任何格式化符号
6. 絕對不要加括號標注，例如（輕聲）、(輕聲)、（停頓）、（嘆氣）等，這些字會被直接朗讀出來
7. 不要使用「嘿」這個字，請改用「嗨」或直接開口說話

请直接输出 DJ 台词，无需前缀或解释。"""

        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "max_tokens": 150,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.95
            }
        )

        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code} - {response.text}")

        result = response.json()
        script_text = result["choices"][0]["message"]["content"].strip()

        return {
            "script": script_text,
            "persona": persona["name"],
            "time_range": persona["time_range"],
            "mood": mood,
            "music_suggestion": persona["music_style"],
            "generated_at": datetime.now().isoformat()
        }

    def _call(self, prompt: str, max_tokens: int = 150) -> str:
        """呼叫 DeepSeek API 的共用方法"""
        response = requests.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}], "temperature": 0.9}
        )
        if response.status_code != 200:
            raise Exception(f"DeepSeek API error: {response.status_code}")
        return response.json()["choices"][0]["message"]["content"].strip()

    def generate_letter_reading(self, messages: List[str], theme: str = "", script_history: List[str] = None) -> Dict:
        """讀一封聽眾的信——回應聊天室裡最有感情的那條留言"""
        persona = self.get_persona_by_time()
        letter = max(messages, key=len) if messages else "今晚好孤單"
        theme_line = f"\n今晚的節目主題是「{theme}」，請讓回應自然呼應這個主題。" if theme else ""
        history_line = ""
        if script_history:
            history_text = "\n".join(f"— {s}" for s in script_history[-2:])
            history_line = f"\n你剛才說過：\n{history_text}\n請自然接續這個氛圍。"

        angle = random.choice(SCRIPT_ANGLES)
        prompt = f"""你是深夜電台 DJ AJ（我是你的朋友 - AJ）。
時段人設：{persona['name']}，語氣：{persona['tone']}{theme_line}{history_line}

你剛收到一封聽眾的留言：
「{letter}」

【切入角度】{angle}

請用 60-90 字回應這封信，像在電台上唸給所有人聽一樣。
先讀出留言的情緒，再用你的方式回應，讓其他聽眾也有共鳴。
直接輸出台詞，不要加任何格式，不要加（輕聲）（停頓）等括號標注，不要使用「嘿」字（改用嗨）。"""

        script = self._call(prompt)
        return {"script": script, "persona": persona["name"],
                "time_range": persona["time_range"], "mode": "letter_reading",
                "music_suggestion": persona["music_style"],
                "generated_at": datetime.now().isoformat()}

    def generate_motivation(self, theme: str = "", script_history: List[str] = None) -> Dict:
        """說一段勵志、溫暖的話"""
        persona = self.get_persona_by_time()
        hour = datetime.now().hour
        theme_line = f"\n今晚的節目主題是「{theme}」，請讓話語自然扣回這個主題。" if theme else ""
        history_line = ""
        if script_history:
            history_text = "\n".join(f"— {s}" for s in script_history[-2:])
            history_line = f"\n你剛才說過：\n{history_text}\n請接著這個節奏說下去。"

        angle = random.choice(SCRIPT_ANGLES)
        prompt = f"""你是深夜電台 DJ AJ（我是你的朋友 - AJ）。
現在是 {hour} 點，時段：{persona['name']}，語氣：{persona['tone']}{theme_line}{history_line}

【切入角度】{angle}

請說一段 60-90 字的溫暖話語。
風格要求：不要說教、不要雞湯感太重，要像一個懂你的老朋友在深夜說話。
用上面的切入角度出發，慢慢說開來。
直接輸出台詞，不要加任何格式，不要加（輕聲）（停頓）等括號標注，不要使用「嘿」字（改用嗨）。"""

        script = self._call(prompt)
        return {"script": script, "persona": persona["name"],
                "time_range": persona["time_range"], "mode": "motivation",
                "music_suggestion": persona["music_style"],
                "generated_at": datetime.now().isoformat()}

    def generate_humor(self, theme: str = "", script_history: List[str] = None) -> Dict:
        """說一個輕鬆幽默的小觀察或冷笑話"""
        persona = self.get_persona_by_time()
        hour = datetime.now().hour
        theme_hint = f"（今晚主題是「{theme}」，可以從這個角度切入）" if theme else ""
        history_line = ""
        if script_history:
            history_text = "\n".join(f"— {s}" for s in script_history[-1:])
            history_line = f"\n你剛才說：{history_text}\n這次換個輕鬆的節奏。"

        angle = random.choice(SCRIPT_ANGLES)
        prompt = f"""你是深夜電台 DJ AJ（我是你的朋友 - AJ）。
現在是 {hour} 點，時段：{persona['name']}{theme_hint}{history_line}

【切入角度】{angle}（用輕鬆幽默的方式詮釋這個角度）

請說一段 50-75 字的輕鬆幽默內容，可以是：
- 關於深夜/失眠的搞笑觀察，帶出一個小故事
- 對加班族/學生族的溫柔吐槽，然後話鋒一轉說句暖的
- 和音樂或電台有關的有趣想法
保持溫暖，不要刻薄。直接輸出台詞，不要加任何格式，不要加（輕聲）（停頓）等括號標注，不要使用「嘿」字（改用嗨）。"""

        script = self._call(prompt)
        return {"script": script, "persona": persona["name"],
                "time_range": persona["time_range"], "mode": "humor",
                "music_suggestion": persona["music_style"],
                "generated_at": datetime.now().isoformat()}

    def generate_song_name(self, mood_analysis: Dict) -> str:
        """為今晚的療癒鋼琴曲生成一個詩意的英文標題（2-4 個單字）"""
        mood = mood_analysis.get("overall_mood", "neutral")
        keywords = mood_analysis.get("keywords", [])[:3]
        kw_str = ", ".join(keywords) if keywords else "night, solitude, warmth"

        prompt = f"""Generate a poetic English title for a late-night healing piano piece.
Mood: {mood}
Atmosphere: {kw_str}

Rules:
- 2 to 4 words only
- Tender, dreamlike, or melancholic
- Suitable for a soft ambient piano piece (not jazz, not upbeat)
- No quotes, no punctuation

Output the title only."""

        return self._call(prompt, max_tokens=20).strip('"\'').strip()

    def generate_song_premiere(self, mood: str = "neutral", song_name: str = "") -> Dict:
        """宣布即將播放為今晚創作的療癒鋼琴曲，自然帶出曲名"""
        persona = self.get_persona_by_time()
        mood_desc = {"melancholic": "帶點憂鬱的", "energetic": "平靜有力的",
                     "neutral": "平靜的", "introspective": "內省的", "mixed": "複雜而溫柔的"}.get(mood, "溫暖的")
        name_mention = f"《{song_name}》" if song_name else "這首曲子"

        prompt = f"""你是深夜電台 DJ AJ（我是你的朋友 - AJ）。
時段：{persona['name']}，語氣：{persona['tone']}
剛剛根據今晚聊天室的氣氛，為大家創作了一首{mood_desc}的療癒鋼琴曲，曲名是 {name_mention}。

請用 35-55 字宣布即將播放這首曲子，像真正的電台 DJ 一樣說話。
自然地帶出曲名，讓聽眾感覺這首曲子是為他們今晚量身創作的。
直接輸出台詞，不要加任何格式，不要加（輕聲）（停頓）等括號標注，不要使用「嘿」字（改用嗨）。"""

        script = self._call(prompt)
        return {"script": script, "persona": persona["name"],
                "time_range": persona["time_range"], "mode": "song_premiere",
                "music_suggestion": persona["music_style"],
                "song_name": song_name,
                "generated_at": datetime.now().isoformat()}

    def generate_by_mode(self, mode: str, messages: List[str] = None,
                         mood_analysis: Dict = None, song_name: str = "",
                         theme: str = "", forced_persona: str = "",
                         script_history: List[str] = None) -> Dict:
        """統一入口：根據 mode 呼叫對應的生成方法"""
        mood_analysis = mood_analysis or {"overall_mood": "neutral",
                                          "dominant_emotion": "neutral", "keywords": []}
        messages = messages or []

        # 若控制台強制指定人設，暫時覆蓋時間判斷
        _orig_get = self.get_persona_by_time
        if forced_persona:
            persona_map = {"evening": self.PERSONAS["evening"],
                           "midnight": self.PERSONAS["midnight"],
                           "late_night": self.PERSONAS["late_night"]}
            if forced_persona in persona_map:
                self.get_persona_by_time = lambda hour=None: persona_map[forced_persona]

        try:
            if mode == "motivation":
                return self.generate_motivation(theme=theme, script_history=script_history)
            elif mode == "humor":
                return self.generate_humor(theme=theme, script_history=script_history)
            elif mode == "song_premiere":
                return self.generate_song_premiere(mood_analysis.get("overall_mood", "neutral"), song_name=song_name)
            else:  # chat_reaction（預設）
                return self.generate_script(mood_analysis, theme=theme, script_history=script_history)
        finally:
            self.get_persona_by_time = _orig_get  # 還原

    def batch_generate(self, messages: List[str], mood_analysis: Dict) -> List[Dict]:
        """
        为多条留言生成个性化回应

        Args:
            messages: 留言列表
            mood_analysis: 聊天室整体情绪分析

        Returns:
            生成的 DJ 文案列表
        """
        scripts = []
        for msg in messages[:3]:  # 最多3条，避免 API 调用过多
            try:
                script = self.generate_script(
                    mood_analysis=mood_analysis,
                    listener_name=self.extract_name(msg),
                    custom_message=msg
                )
                scripts.append(script)
            except Exception as e:
                print(f"Error generating script for '{msg}': {e}")
                continue

        return scripts

    @staticmethod
    def extract_name(message: str) -> str:
        """
        尝试从留言中提取名字（简单启发式）

        Args:
            message: 留言文本

        Returns:
            提取的名字或 None
        """
        # 简单的 @ 提及检测
        if "@" in message:
            parts = message.split("@")
            if len(parts) > 1:
                name = parts[1].split()[0]
                if len(name) <= 20:  # 合理的名字长度
                    return name
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DJ Script Generator")
    parser.add_argument("--mood", default="melancholic", help="Overall mood")
    parser.add_argument("--listener", help="Listener name")
    parser.add_argument("--message", help="Custom message")
    parser.add_argument("--hour", type=int, help="Hour of day (0-23)")

    args = parser.parse_args()

    try:
        generator = DJScriptGenerator()

        # 创建 mock 情绪分析数据
        mock_mood = {
            "overall_mood": args.mood,
            "dominant_emotion": "tired",
            "keywords": ["work", "sleep", "lonely"],
            "confidence": 0.85
        }

        result = generator.generate_script(
            mood_analysis=mock_mood,
            listener_name=args.listener,
            custom_message=args.message
        )

        print("\n" + "="*60)
        print(f"【{result['persona']}】{result['time_range']}")
        print("="*60)
        print(f"\n气氛：{result['mood']}")
        print(f"音乐建议：{result['music_suggestion']}")
        print(f"\n📻 DJ 台词：\n{result['script']}")
        print("\n" + "="*60)

    except Exception as e:
        print(f"Error: {e}")
