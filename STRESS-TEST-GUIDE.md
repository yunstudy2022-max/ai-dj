# claudio.fm 压力测试指南

## Task 2.7 — 本地 2 小时压力测试

这是 Phase 2 的最后一步，验证整个系统在连续运行中的稳定性和性能。

---

## 测试目标

### 主要检查项

1. **内存泄漏检测**
   - 监控 Python 进程内存使用
   - 检测是否存在线性增长
   - 目标：峰值不超过 1GB，无明显泄漏趋势

2. **API 调用成功率**
   - DeepSeek-V4（情绪分析）
   - Claude 3.5 Sonnet（DJ 文案）
   - Suno API（音乐提示词）
   - 异步队列系统
   - 目标：>95% 成功率

3. **音频同步状态**
   - DJ 讲话 + 音乐生成的时间线
   - 过渡音乐的无缝切换
   - 队列中项目的状态流转

4. **前端 UI 响应性**
   - WebSocket 推送延迟
   - 实时更新的稳定性

---

## 前置准备

### 1. 环境配置

```powershell
# 创建 .env 文件
cd P:\我的雲端硬碟\🟆AI發想區\AIDJ直播間
cp .env.example .env
```

编辑 `.env` 填入 API 密钥：
```
DEEPSEEK_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...
SUNO_API_KEY=...
```

### 2. 安装依赖

```powershell
pip install requests python-dotenv psutil websockets
```

### 3. 启动 OBS（可选）

如果要测试推流集成：
```powershell
# 启动 OBS Studio
# Tools → WebSocket Server Settings → Enable WebSocket server
```

---

## 运行测试

### 快速测试（5 分钟）

```powershell
python scripts/stress-test.py --duration 5
```

**用途**：快速验证系统可用性和基本功能

### 标准测试（2 小时）

```powershell
python scripts/stress-test.py --duration 120
```

**用途**：完整的稳定性和性能评估

### 自定义时长

```powershell
# 30 分钟测试
python scripts/stress-test.py --duration 30

# 4 小时长期测试
python scripts/stress-test.py --duration 240
```

---

## 测试流程

### 测试步骤

```
[初始化引擎]
    ↓
[启动系统监控] ← 内存、CPU
    ↓
[主循环（5秒采样周期）]
    ├─ 生成 6-12 条模拟聊天
    ├─ 调用完整处理流程
    │  ├─ 情绪分析 (DeepSeek)
    │  ├─ DJ 文案生成 (Claude)
    │  ├─ 音乐提示词 (Suno 参数)
    │  └─ 异步队列管理
    ├─ 记录 API 性能指标
    ├─ 更新系统监控数据
    └─ 每 30 秒输出进度统计
    ↓
[生成详细报告]
    ├─ 内存泄漏检测
    ├─ API 性能统计
    ├─ 音频同步分析
    └─ JSON 报告输出
```

### 实时输出示例

```
🧪 启动 120.0 分钟压力测试
════════════════════════════════════════════════════════════

📦 初始化 claudio.fm 引擎...

模块状态：
  emotion_analyzer: ✅
  dj_generator: ✅
  music_generator: ✅
  orchestrator: ✅

▶️  开始处理聊天和生成内容...

📊 进度：1.4% (1.7分 / 剩余 118.3分)
   内存：245/512 MB
   CPU：15.2%
   批次：21 (错误：0)
   API 成功率：100.0%
```

---

## 报告解读

### 生成的报告

测试完成后会生成 JSON 报告，文件名格式：
```
stress_test_20260511_143022.json
```

### 报告结构

```json
{
  "test_metadata": {
    "duration_minutes": 120,
    "start_time": "2026-05-11T14:30:22",
    "end_time": "2026-05-11T16:30:22"
  },
  "system_health": {
    "current_memory_mb": 245,
    "peak_memory_mb": 512,
    "average_memory_mb": 280,
    "average_cpu_percent": 18.5
  },
  "api_performance": {
    "emotion_analysis": {
      "total_calls": 1440,
      "success_rate": 100.0,
      "avg_response_ms": 2850
    },
    "dj_script_generation": {
      "total_calls": 1440,
      "success_rate": 99.8,
      "avg_response_ms": 3200
    }
  },
  "issues": {
    "memory_leak_detected": false,
    "sync_issues": []
  }
}
```

### 关键指标解读

| 指标 | 目标值 | 说明 |
|-----|------|------|
| 内存峰值 | <1000 MB | 无明显泄漏 |
| CPU 平均 | <30% | 正常负荷 |
| API 成功率 | >95% | 系统稳定 |
| 响应时间 P95 | <5000ms | 可接受延迟 |
| 内存增长趋势 | <50 MB/小时 | 无泄漏 |

---

## 常见问题

### Q1: 测试中出现 API 超时错误

**症状**：`DeepSeek API timeout`

**原因**：
- API 限流（达到 QPM 或 RPM 上限）
- 网络不稳定
- API 服务异常

**解决**：
- 检查 API 配额使用情况
- 增加 API 间隔时间
- 检查网络连接

### Q2: 内存持续增长

**症状**：内存从 200MB 增长到 800MB

**诊断**：
```python
# 检查是否为泄漏
from monitoring import SystemMonitor
monitor = SystemMonitor()
# 运行测试后检查：
monitor.detect_memory_leak(threshold_mb=50)
```

**可能原因**：
- 列表/队列未及时清理
- 缓存不清空

### Q3: 音频同步不稳定

**症状**：DJ 讲话和音乐间有明显间隙

**检查**：
- 检查异步队列的过渡音乐是否触发
- 验证音乐生成的平均时间
- 检查 Suno API 的响应延迟

---

## 性能优化建议

### 如果测试结果不理想

#### 内存优化
```python
# 在 emotion-analyzer.py 中定期清空缓存
self.cache.clear() if len(self.cache) > 1000 else None
```

#### API 性能优化
```python
# 增加重试机制和超时时间
timeout = 30  # 增加到 30 秒
max_retries = 3
```

#### 队列优化
```python
# 增加队列大小限制
max_queue_size = 100
# 定期清理已完成的项目
self.queue = [item for item in self.queue if item.status != AudioItemStatus.COMPLETED]
```

---

## 监控仪表板（可选）

如果需要实时监控，可以创建一个简单的 Web 仪表板：

```python
# 创建 dashboard.py
from flask import Flask, jsonify
from monitoring import PerformanceReport

app = Flask(__name__)
report = PerformanceReport()

@app.route('/stats')
def get_stats():
    return jsonify(report.system_monitor.get_stats())

app.run(port=5000)
```

然后访问 `http://localhost:5000/stats` 查看实时统计。

---

## 压力测试清单

- [ ] 环境配置（.env 填入 API 密钥）
- [ ] 依赖安装（pip install）
- [ ] 快速测试通过（--duration 5）
- [ ] 完整测试启动（--duration 120）
- [ ] 监控进度输出
- [ ] 测试完成，报告生成
- [ ] 报告分析，确认系统稳定
- [ ] 记录优化建议

---

## 后续步骤

### Phase 3 — 商业化准备

压力测试通过后，可以进行：

1. **云端部署准备**
   - 配置 AWS / 阿里云 / Azure
   - 数据库持久化
   - 日志和监控系统

2. **前端 WebSocket 集成**
   - 实时推送架构
   - 前端 UI 更新

3. **YouTube 直播集成**
   - 实现 Task 2.1（YouTube Chat API）
   - 真实直播测试

4. **常客识别系统**
   - 用户身份追踪
   - 个性化记忆

---

*最后更新：2026-05-11*
