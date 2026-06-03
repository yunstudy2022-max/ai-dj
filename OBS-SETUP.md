# OBS WebSocket 设置指南

## 前提条件

### 1. 安装 OBS Studio
下载：https://obsproject.com/
- Windows：OBS-Studio-*.exe
- 安装完成后启动 OBS

### 2. 安装 OBS WebSocket 插件

**方法 A：通过 OBS 内置插件管理器（推荐）**
1. 打开 OBS Studio
2. 菜单：**Tools** → **Plugins**
3. 搜索 "WebSocket"
4. 找到 "obs-websocket"，点击 **Install**
5. 重启 OBS

**方法 B：手动安装**
1. 下载：https://github.com/obsproject/obs-websocket/releases
2. 解压到 OBS 插件目录
3. 重启 OBS

### 3. 启用 WebSocket Server

1. OBS 菜单：**Tools** → **WebSocket Server Settings**
2. 勾选：✓ **Enable WebSocket server**
3. 设置：
   - Server Port: **4444**（默认）
   - Enable Authentication: 可选（本地测试可禁用）
4. 点击 **Apply**

### 4. 验证连接

```powershell
# 测试 WebSocket 连接
python scripts/obs-controller.py --test
```

如果输出显示 `✅ OBS WebSocket 已连接`，则设置成功。

---

## 使用方式

### Python 脚本调用

```python
from obs_controller import OBSBroadcastController

controller = OBSBroadcastController()
await controller.initialize()

# 启动直播
await controller.start_broadcast(scene_name="直播场景", virtual_camera=True)

# 停止直播
await controller.stop_broadcast()
```

### 命令行使用

```powershell
# 查询状态
python obs-controller.py --status

# 启动推流
python obs-controller.py --start-stream

# 停止推流
python obs-controller.py --stop-stream

# 运行测试
python obs-controller.py --test
```

---

## 完整的直播流程

### Phase 2 系统流程

```
[YouTube 聊天] → [情绪分析] → [DJ 文案] → [音乐生成]
                                              ↓
                                    [异步队列管理]
                                              ↓
                                  [OBS 推流控制] ← [this module]
                                              ↓
                                      [直播输出]
```

### claudio.fm 启动脚本（伪代码）

```python
async def run_live_broadcast(duration_hours=2):
    # 1. 初始化所有模块
    engine = ClaudioFMEngine()
    obs = OBSBroadcastController()
    
    await obs.initialize()
    
    # 2. 启动 OBS 推流
    await obs.start_broadcast(
        scene_name="claudio.fm 直播间",
        virtual_camera=True
    )
    
    # 3. 主循环：每 5 秒抓取并处理一批聊天
    start_time = time.time()
    while time.time() - start_time < duration_hours * 3600:
        messages = await fetch_youtube_chat()
        
        # 处理聊天 → 生成 DJ → 音乐 → 推送到前端
        result = await engine.process_youtube_chat_batch(messages)
        
        await asyncio.sleep(5)
    
    # 4. 停止推流
    await obs.stop_broadcast()
```

---

## 故障排查

### 连接失败

**症状**：`❌ 连接失败: [Errno 10061] No connection could be made`

**解决方案**：
- ✓ OBS 是否启动？
- ✓ WebSocket Server 是否已启用？
- ✓ 端口 4444 是否被占用？

```powershell
# 检查端口占用
netstat -ano | findstr :4444
```

### 认证失败

**症状**：`❌ OBS WebSocket 认证失败`

**解决方案**：
- 检查 `.env` 文件中的 `OBS_WEBSOCKET_PASSWORD`
- 如果 OBS 中未启用密码，不需要密码

### 推流不工作

**症状**：推流命令成功但 YouTube 不显示流

**解决方案**：
- ✓ YouTube Studio 中的流密钥是否已设置？
- ✓ 网络连接是否正常？
- ✓ OBS 输出设置（Settings → Stream）是否正确配置？

---

## 支持的命令

| 命令 | 功能 |
|-----|------|
| `start_stream()` | 启动推流到 YouTube |
| `stop_stream()` | 停止推流 |
| `start_virtual_camera()` | 启动虚拟摄像头 |
| `stop_virtual_camera()` | 停止虚拟摄像头 |
| `set_current_scene(name)` | 切换场景 |
| `get_current_scene()` | 获取当前场景 |
| `set_input_volume(name, db)` | 设置音量 |
| `get_stream_status()` | 获取推流状态 |
| `get_obs_stats()` | 获取 OBS 统计（CPU、内存等） |

---

## 性能监控

OBS 推流监控指标：

- **CPU 使用率**：应保持在 30-50% 以下
- **内存使用**：应保持在 500-1000 MB 以下
- **丢帧率**：应为 0（或 <1%）
- **平均帧时间**：应 <33ms（30 FPS）

```python
stats = await obs.get_obs_stats()
print(f"CPU: {stats.get('cpuUsage')}%")
print(f"Memory: {stats.get('memoryUsage')} MB")
print(f"Dropped frames: {stats.get('totalStreamTime')}")
```

---

## 本地测试步骤

1. 在 OBS 中创建一个测试场景 "claudio.fm 直播间"
2. 运行：`python scripts/obs-controller.py --test`
3. 应看到：
   ```
   ✅ OBS WebSocket 已连接
   ✅ 虚拟摄像头已启动
   ✅ 推流已启动
   ... [等待 3 秒] ...
   ✅ 推流已停止
   ✅ 虚拟摄像头已停止
   ```

---

## 高级配置

### 自定义虚拟音轨

OBS 支持多个虚拟音轨用于分离音频。在 claudio.fm 中：
- **音轨 1**：DJ 讲话（TTS）
- **音轨 2**：背景音乐（Suno）
- **音轨 3**：过渡音乐（环境音）

配置方法：
1. OBS → Settings → Audio
2. 启用多个虚拟音轨
3. 在 Python 中调用 `set_input_volume(audio_track, volume_db)`

---

*更新于 2026-05-11*
