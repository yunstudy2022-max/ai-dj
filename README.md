# claudio.fm — AI DJ 深夜電台

> **我是你的朋友 · AJ** — 一個為深夜而生的 AI 電台主持人

*A fully automated AI radio DJ system for late-night listeners who need company.*

---

## 是什麼 · What is this

**claudio.fm** 是一套完全自動化的 AI 電台系統。AJ 是一位有品味、有溫度的 AI DJ，在深夜為加班族、失眠者、需要陪伴的人播報、說話、生成專屬音樂。

**claudio.fm** is a fully automated AI radio system. AJ is a thoughtful, warm AI DJ who broadcasts, talks, and generates original music for late-night listeners — the overworked, the sleepless, and those who just need company.

---

## 功能特色 · Features

| 功能 | 說明 |
|------|------|
| 🎙️ AI DJ 台詞 | DeepSeek 生成 60–90 字深夜風格台詞，17 種切入角度隨機輪換 |
| 🔊 語音合成 | ElevenLabs `eleven_v3` 模型，中文語調自然 |
| 🎵 即時作曲 | Suno API 根據聊天室情緒生成療癒鋼琴曲，自動命名存檔 |
| 💬 情緒分析 | 讀取聊天室訊息 → 分析情緒 → 對應音樂風格 |
| 🛡️ 聊天審查 | 雙層過濾：本地關鍵字黑名單 + DeepSeek 語意審查 |
| 🌙 三段時段人設 | 晚安下班了 / 深夜吧檯 / I人的時光，語氣自動切換 |
| 🎛️ 管理控制台 | 設定主題、廣播間隔、音色、音樂風格、Suno 開關 |

---

## 技術架構 · Tech Stack

```
前端 Frontend    React 18 (CDN) + Babel Standalone — 單一 HTML 檔案，無需建置
後端 Backend     FastAPI + WebSocket — Python，Windows 本地執行
DJ 文案          DeepSeek-V4 API（OpenAI 相容格式）
語音合成 TTS     ElevenLabs API（eleven_v3 模型）
音樂生成         Suno via sunoapi.org
直播推流         OBS + YouTube Live
```

---

## 系統流程 · Pipeline

```
Auto-pilot 計時
      ↓
① 情緒分析   聊天室訊息 → DeepSeek 分析情緒與關鍵詞
      ↓
② 台詞生成   情緒 + 時段人設 + 隨機切入角度 → AJ 台詞
      ↓
③ TTS 合成   ElevenLabs 生成語音 → 前端播放       ← 聽眾聽到 AJ 說話
      ↓（同時背景執行）
④ 音樂生成   情緒 → 音樂風格關鍵詞 → Suno 生成療癒鋼琴曲
      ↓
  music_ready → 前端切換背景音樂
```

---

## 快速開始 · Quick Start

### 1. 安裝依賴

```bash
pip install fastapi uvicorn python-dotenv requests httpx
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env`，填入各服務的 API Key：

```bash
cp .env.example .env
```

```env
DEEPSEEK_API_KEY=your-deepseek-key
ELEVENLABS_API_KEY=your-elevenlabs-key
SUNO_API_KEY=your-suno-key
YOUTUBE_API_KEY=your-youtube-key   # 接入真實聊天室時需要
```

### 3. 啟動伺服器

```bash
python -X utf8 scripts/server.py
```

### 4. 開啟瀏覽器

```
http://localhost:8000
```

設定今晚的主題，點選「進入電台」，AJ 開始說話。

---

## 專案結構 · Project Structure

```
claudio.fm/
├── AI DJ/
│   └── claudio-fm-index.html   # 前端主介面（React 單頁應用）
├── scripts/
│   ├── server.py               # FastAPI 後端 + WebSocket
│   ├── dj-script-generator.py  # DJ 台詞生成引擎
│   ├── elevenlabs-tts.py       # TTS 語音合成
│   ├── emotion-analyzer.py     # 聊天室情緒分析
│   ├── suno-client.py          # Suno 音樂生成客戶端
│   ├── chat-moderator.py       # 聊天室審查系統
│   └── blacklist.json          # 本地關鍵字黑名單
├── 開發文件/                    # 系統設計文件
├── .env.example                # 環境變數範本
└── README.md
```

---

## 三段時段人設 · Time-based Personas

| 時段 | 名稱 | 氣質 |
|------|------|------|
| 18:00–21:00 | 晚安下班了 | 溫暖、活力、卸下裝備 |
| 21:00–00:00 | 深夜吧檯 | 故事感、微醺、話不多但句句見血 |
| 00:00–03:00 | I人的時光 | 輕聲細語、無壓力陪伴、絕對獨處感 |

---

## API 依賴 · Required APIs

- [DeepSeek](https://platform.deepseek.com/) — DJ 文案生成 + 情緒分析
- [ElevenLabs](https://elevenlabs.io/) — 語音合成（TTS）
- [Suno via sunoapi.org](https://sunoapi.org/) — AI 音樂生成
- [YouTube Data API](https://developers.google.com/youtube) — 直播聊天接入（選用）

---

## 開發進度 · Roadmap

- [x] 前端 UI（Wabi-sabi 風格）
- [x] WebSocket 即時推送
- [x] DJ 台詞 + TTS + Suno 完整流程
- [x] 聊天室情緒分析 → 音樂風格對應
- [x] 管理控制台
- [ ] YouTube 真實聊天室接入
- [ ] 雲端部署（Docker / Railway）

---

## 授權 · License

MIT License — 歡迎 fork 自己開一台深夜電台。

---

*Built with Claude Code · 為那些深夜還醒著的人*
