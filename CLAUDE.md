# claudio.fm — AI DJ 深夜電台系統

## 🎯 项目目标
构建一个完全自动化的 AI DJ 电台系统，能 24/7 无人值守运行，通过抓取 YouTube 直播聊天、分析观众情绪、自动生成 DJ 语音和背景音乐，为深夜听众提供温暖的陪伴和精心策划的音乐体验。

## 🏗️ 项目架构
- **前端**：React + Wabi-sabi 美学 UI（已完成初版）
- **后端**：Python 核心引擎（WSL Ubuntu）
- **推流**：OBS + YouTube Live
- **API**：Claude、ElevenLabs、Suno、YouTube Data API

## 📋 当前阶段
**Phase 1 - MVP 验证**（进行中）
- ✅ 前端 UI 完成（claudio-fm-index.html）
- ⏳ 后端核心开发中
- ⏳ API 串接测试
- ⏳ 本地 2 小时直播测试

## 🚀 启动流程
1. 更新 MEMORY.md 中的项目进度
2. 检查最新任务清单（tasks/）
3. 执行当前的开发任务
4. 完成后自动更新成功记录和错误日志

## 📂 相关目录
- `MEMORY.md` — 记忆总索引
- `tasks/` — 任务流程和执行报告
- `docs/` — 知识库和参考文档
- `scripts/` — 可重用的技能脚本
- `errors.md` — 错误记录
- `successes.md` — 成功记录

## ⚙️ 工作模式
优先级顺序：
1. 完成当前 Phase 1 前端
2. 开发后端 Python 引擎
3. 串接外部 API
4. 本地压力测试
5. 云端部署准备
