# claudio.fm 快速开始指南

## 30 秒快速演示

```powershell
# 1. 确保有 .env 文件（包含 API 密钥）
cp .env.example .env
# 编辑 .env，填入：
# DEEPSEEK_API_KEY=sk-...
# CLAUDE_API_KEY=sk-ant-...

# 2. 安装依赖
pip install requests python-dotenv psutil websockets

# 3. 运行本机演示
python scripts/demo.py --quick      # 1 轮快速演示（1-2 分钟）
python scripts/demo.py --extended   # 5 轮完整演示（5-10 分钟）
```

---

## 演示流程

### 单轮演示包含什么

```
【输入】YouTube 聊天消息 5 条
   ↓
【Step 1】情绪分析（DeepSeek-V4）
   └─ 输出：整体气氛、主导情绪、关键词
   ↓
【Step 2】DJ 文案生成（Claude）
   └─ 输出：30-50 字温暖台词
   ↓
【Step 3】音乐提示词（Suno 参数）
   └─ 输出：音乐特征参数 + 缓存状态
   ↓
【Step 4】异步队列管理
   └─ 输出：生成策略、时间线规划
```

### 输出示例

```
🎬 claudio.fm 本机演示
════════════════════════════════════════════════════════════

📦 初始化后端引擎...

✅ 模块状态检查：
   emotion_analyzer: ✅
   dj_generator: ✅
   music_generator: ✅
   orchestrator: ✅

════════════════════════════════════════════════════════════
📨 批次 1/1
════════════════════════════════════════════════════════════

💬 接收到 5 条聊天消息：
   1. 今晚加班好累
   2. 压力太大了
   3. 工作一整天，困死了
   4. 又是加班的一天
   5. 什么时候才能休息

⚙️  处理流程：

✅ 处理成功

📊 [1/4] 情绪分析
   整体气氛：melancholic
   主导情绪：tired
   关键词：work, tired, sleep
   信心度：87.0%

📻 [2/4] DJ 文案生成【I人的时光】
   "有时候，靜靜聽著就夠了。看你们加班这么辛苦，这首曲子献给今晚还醒著的你。"
   字数：41

🎵 [3/4] 音乐生成参数
   提示词：Ambient, sparse piano, vinyl crackle, slow...
   缓存：❌ 新建

⚙️  [4/4] 异步队列管理
   生成策略：fallback
   队列项目：3 个

⏱️  时间线规划：
   • dj_speech: 0-5s
   • fallback_audio: 5-60s
   • music_expected: 60s (when ready)

════════════════════════════════════════════════════════════
✅ 演示完成
════════════════════════════════════════════════════════════

📋 演示总结：
   • 完成批次：1
   • 总聊天消息：5
   • 处理流程：情绪分析 → DJ 文案 → 音乐参数 → 异步队列
   • 系统状态：✅ 正常
```

---

## 常见问题

### Q1: 运行时出现 API 错误

```
❌ emotion_analyzer: ❌ 情绪分析初始化失败
```

**解决**：检查 `.env` 文件
```powershell
# 查看是否有 .env 文件
ls .env

# 检查内容
type .env

# 确保包含：
DEEPSEEK_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...
```

### Q2: 没有 DeepSeek API 怎么办

**临时方案**：使用模拟数据（修改 demo.py）
```python
# 在 setup() 中跳过初始化检查
# if self.engine.emotion_analyzer is None:
#     return False  # 改为继续
```

**正式方案**：注册 DeepSeek API
- https://platform.deepseek.com/
- 申请 API 密钥
- 配置到 `.env`

### Q3: 演示速度很慢

正常情况下：
- 第 1 批：10-15 秒（首次初始化）
- 第 2-5 批：5-8 秒（缓存命中）

总共 5 轮约 5-10 分钟。

---

## 演示后的测试步骤

### Step 1: 运行单模块测试

```powershell
# 情绪分析单独测试
python scripts/test-emotion.py

# DJ 文案单独测试
python scripts/test-dj-script.py

# 音乐参数单独测试
python scripts/test-music-generator.py

# 队列管理单独测试
python scripts/test-queue.py
```

### Step 2: 运行完整压力测试

```powershell
# 5 分钟快速压力测试
python scripts/stress-test.py --duration 5

# 2 小时完整压力测试
python scripts/stress-test.py --duration 120
```

### Step 3: 配置 OBS（可选）

```powershell
# 测试 OBS WebSocket 连接
python scripts/test-obs.py

# 配置说明
cat OBS-SETUP.md
```

---

## 系统要求

### 最低配置
- Python 3.7+
- 4GB 内存
- 50MB 磁盘空间
- 网络连接

### 推荐配置
- Python 3.9+
- 8GB 内存
- 100MB 磁盘空间
- 稳定的互联网（API 调用）

---

## 演示内容速查

| 想看什么 | 运行什么 |
|--------|--------|
| 完整系统演示 | `python scripts/demo.py --quick` |
| 5 轮演示 | `python scripts/demo.py --extended` |
| 情绪分析效果 | `python scripts/test-emotion.py` |
| DJ 文案生成 | `python scripts/test-dj-script.py` |
| 音乐参数生成 | `python scripts/test-music-generator.py` |
| 队列管理演示 | `python scripts/test-queue.py` |
| 2 小时压力测试 | `python scripts/stress-test.py --duration 120` |

---

## 架构简图

```
YouTube 聊天模拟
    ↓
[情绪分析] ← DeepSeek API
    ↓
[DJ 文案生成] ← Claude API
    ↓
[音乐参数生成] ← Suno 参数
    ↓
[异步队列管理] ← 过渡音乐
    ↓
[推流控制] ← OBS WebSocket
    ↓
实时直播输出
```

---

## 完整文档导航

| 文档 | 内容 |
|------|------|
| PHASE-2-SUMMARY.md | Phase 2 完整总结和架构说明 |
| OBS-SETUP.md | OBS 配置和推流集成 |
| STRESS-TEST-GUIDE.md | 2 小时压力测试说明 |
| CLAUDE.md | 项目初始化文件 |
| MEMORY.md | 项目记忆和进度跟踪 |

---

## 后续步骤

演示完成后的建议：

1. **验证 API 配额**
   - DeepSeek：确保有足够的 credit
   - Claude：检查 API 可用性
   - 预算考虑（2 小时测试成本 ~$5-10）

2. **配置直播环境**
   - OBS Studio 安装
   - YouTube 频道设置
   - 推流密钥配置

3. **准备真实直播**
   - 完成 Task 2.1（YouTube Chat API）
   - 前端 WebSocket 推送
   - 数据库持久化

---

## 技术支持

### 查看日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 检查系统状态

```python
from integration_engine import ClaudioFMEngine
engine = ClaudioFMEngine()
print(engine.get_system_status())
```

### 性能监控

```python
from monitoring import SystemMonitor
monitor = SystemMonitor()
monitor.start()
# ... 运行演示 ...
stats = monitor.get_stats()
print(stats)
```

---

## 成功标志

演示完成后应该看到：

✅ 5 条聊天消息被成功分析
✅ 生成了个性化的 DJ 台词
✅ 生成了音乐参数提示词
✅ 异步队列规划了时间线
✅ 没有 API 错误（仅 DeepSeek 和 Claude 配置正确）

如果看到这些，说明系统已准备就绪！

---

*最后更新：2026-05-11*
