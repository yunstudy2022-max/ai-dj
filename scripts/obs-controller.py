"""
Task 2.6 — OBS WebSocket 集成
自动控制 OBS 推流、虚拟摄像头、音轨设置

前提条件：
  1. 安装 OBS Studio（https://obsproject.com/）
  2. 安装 OBS WebSocket 插件（Tools → WebSocket Server Settings）
  3. 启用 WebSocket Server（默认 ws://localhost:4444）

使用方式：
  python obs-controller.py --status
  python obs-controller.py --start-stream
  python obs-controller.py --stop-stream
"""

import os
import json
import asyncio
import websockets
import hashlib
import base64
import uuid
from typing import Dict, Optional, Callable
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class OBSWebSocketClient:
    """OBS WebSocket 客户端"""

    def __init__(
        self,
        url: str = None,
        password: str = None,
        auto_reconnect: bool = True
    ):
        """
        初始化 OBS WebSocket 客户端

        Args:
            url: WebSocket URL（默认 ws://localhost:4444）
            password: WebSocket 密码（如果启用）
            auto_reconnect: 是否自动重连
        """
        self.url = url or os.getenv("OBS_WEBSOCKET_URL", "ws://localhost:4444")
        self.password = password or os.getenv("OBS_WEBSOCKET_PASSWORD")
        self.auto_reconnect = auto_reconnect

        self.ws = None
        self.session_id = None
        self.callbacks: Dict[str, list] = {
            "connected": [],
            "disconnected": [],
            "stream_state_changed": [],
            "virtual_camera_state_changed": [],
            "error": []
        }

        self.message_id_counter = 0
        self.pending_responses: Dict[int, Dict] = {}

    async def connect(self) -> bool:
        """
        连接到 OBS WebSocket Server

        Returns:
            是否连接成功
        """
        try:
            print(f"🔗 连接到 OBS WebSocket: {self.url}")
            self.ws = await websockets.connect(self.url)

            # 接收 ServerHello 消息
            hello = await self.ws.recv()
            hello_data = json.loads(hello)

            print(f"✅ OBS WebSocket 已连接")
            print(f"   OBS 版本：{hello_data.get('d', {}).get('obsVersion')}")
            print(f"   WebSocket 版本：{hello_data.get('d', {}).get('websocketVersion')}")

            # 认证（如果需要）
            if hello_data.get("d", {}).get("authentication"):
                await self._authenticate(hello_data)

            # 启动接收消息循环
            asyncio.create_task(self._receive_loop())

            self._trigger_callback("connected", {})
            return True

        except Exception as e:
            print(f"❌ 连接失败：{e}")
            self._trigger_callback("error", {"error": str(e)})
            return False

    async def _authenticate(self, hello_data: Dict):
        """处理 WebSocket 认证"""
        if not self.password:
            raise Exception("OBS WebSocket 需要密码，但未提供")

        auth_data = hello_data.get("d", {}).get("authentication", {})
        challenge = auth_data.get("challenge")
        salt = auth_data.get("salt")

        # 生成认证信息
        secret = hashlib.sha256(
            (self.password + salt).encode()
        ).digest()
        auth_hash = base64.b64encode(
            hashlib.sha256(secret + challenge.encode()).digest()
        ).decode()

        # 发送认证
        await self.send_message(
            request_type="Identify",
            request_data={"rpcVersion": 1, "authentication": auth_hash}
        )

        print("✅ OBS WebSocket 认证成功")

    async def send_message(
        self,
        request_type: str,
        request_data: Dict = None,
        wait_response: bool = True
    ) -> Optional[Dict]:
        """
        发送 WebSocket 消息

        Args:
            request_type: 请求类型
            request_data: 请求数据
            wait_response: 是否等待响应

        Returns:
            响应数据
        """
        if not self.ws:
            raise Exception("未连接到 OBS WebSocket")

        self.message_id_counter += 1
        message_id = self.message_id_counter

        message = {
            "op": 6,  # WebSocketOpCode.Request
            "d": {
                "requestType": request_type,
                "requestId": str(message_id),
                "requestData": request_data or {}
            }
        }

        await self.ws.send(json.dumps(message))

        if wait_response:
            # 等待响应
            timeout = 30  # 30 秒超时
            start_time = asyncio.get_event_loop().time()

            while message_id in self.pending_responses:
                await asyncio.sleep(0.1)
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise Exception(f"Request {message_id} timeout")

            return self.pending_responses.pop(message_id, None)

        return None

    async def _receive_loop(self):
        """接收消息循环"""
        try:
            while self.ws:
                message = await self.ws.recv()
                data = json.loads(message)

                op_code = data.get("op")

                if op_code == 7:  # WebSocketOpCode.RequestResponse
                    request_id = int(data.get("d", {}).get("requestId", 0))
                    self.pending_responses[request_id] = data.get("d", {})

                elif op_code == 8:  # WebSocketOpCode.RequestBatch
                    # 处理批量响应
                    pass

                elif op_code == 0:  # WebSocketOpCode.Hello
                    # 服务器 Hello
                    pass

        except Exception as e:
            print(f"❌ 接收循环错误：{e}")
            await self.disconnect()

    async def disconnect(self):
        """断开连接"""
        if self.ws:
            await self.ws.close()
            self.ws = None
        self._trigger_callback("disconnected", {})

    # ============= 推流控制 =============

    async def start_stream(self) -> bool:
        """启动推流"""
        try:
            result = await self.send_message("StartStream")
            print("✅ 推流已启动")
            self._trigger_callback("stream_state_changed", {"state": "streaming"})
            return True
        except Exception as e:
            print(f"❌ 启动推流失败：{e}")
            return False

    async def stop_stream(self) -> bool:
        """停止推流"""
        try:
            result = await self.send_message("StopStream")
            print("✅ 推流已停止")
            self._trigger_callback("stream_state_changed", {"state": "stopped"})
            return True
        except Exception as e:
            print(f"❌ 停止推流失败：{e}")
            return False

    async def get_stream_status(self) -> Dict:
        """获取推流状态"""
        try:
            result = await self.send_message("GetStreamStatus")
            return result.get("responseData", {})
        except Exception as e:
            print(f"❌ 获取推流状态失败：{e}")
            return {}

    # ============= 虚拟摄像头控制 =============

    async def start_virtual_camera(self) -> bool:
        """启动虚拟摄像头"""
        try:
            result = await self.send_message("StartVirtualCamera")
            print("✅ 虚拟摄像头已启动")
            self._trigger_callback(
                "virtual_camera_state_changed",
                {"state": "active"}
            )
            return True
        except Exception as e:
            print(f"❌ 启动虚拟摄像头失败：{e}")
            return False

    async def stop_virtual_camera(self) -> bool:
        """停止虚拟摄像头"""
        try:
            result = await self.send_message("StopVirtualCamera")
            print("✅ 虚拟摄像头已停止")
            self._trigger_callback(
                "virtual_camera_state_changed",
                {"state": "inactive"}
            )
            return True
        except Exception as e:
            print(f"❌ 停止虚拟摄像头失败：{e}")
            return False

    # ============= 场景控制 =============

    async def get_current_scene(self) -> Optional[str]:
        """获取当前场景"""
        try:
            result = await self.send_message("GetCurrentProgramScene")
            return result.get("responseData", {}).get("currentProgramSceneName")
        except Exception as e:
            print(f"❌ 获取当前场景失败：{e}")
            return None

    async def set_current_scene(self, scene_name: str) -> bool:
        """设置当前场景"""
        try:
            await self.send_message(
                "SetCurrentProgramScene",
                {"sceneName": scene_name}
            )
            print(f"✅ 已切换到场景：{scene_name}")
            return True
        except Exception as e:
            print(f"❌ 切换场景失败：{e}")
            return False

    # ============= 音轨控制 =============

    async def get_input_volume(self, input_name: str) -> Optional[float]:
        """获取输入音量"""
        try:
            result = await self.send_message(
                "GetInputVolume",
                {"inputName": input_name}
            )
            return result.get("responseData", {}).get("volumeDb")
        except Exception as e:
            print(f"❌ 获取音量失败：{e}")
            return None

    async def set_input_volume(self, input_name: str, volume_db: float) -> bool:
        """设置输入音量"""
        try:
            await self.send_message(
                "SetInputVolume",
                {"inputName": input_name, "volumeDb": volume_db}
            )
            print(f"✅ {input_name} 音量已设置为 {volume_db} dB")
            return True
        except Exception as e:
            print(f"❌ 设置音量失败：{e}")
            return False

    # ============= 回调系统 =============

    def register_callback(self, event: str, callback: Callable):
        """注册回调函数"""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)

    def _trigger_callback(self, event: str, data: Dict):
        """触发回调"""
        for callback in self.callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Callback error: {e}")

    # ============= 系统状态 =============

    async def get_obs_stats(self) -> Dict:
        """获取 OBS 统计信息"""
        try:
            result = await self.send_message("GetStats")
            return result.get("responseData", {})
        except Exception as e:
            print(f"❌ 获取统计信息失败：{e}")
            return {}


class OBSBroadcastController:
    """OBS 广播控制器 — 管理推流生命周期"""

    def __init__(self):
        """初始化控制器"""
        self.obs = OBSWebSocketClient()
        self.is_broadcasting = False
        self.broadcast_start_time = None

    async def initialize(self) -> bool:
        """初始化 OBS 连接"""
        return await self.obs.connect()

    async def start_broadcast(
        self,
        scene_name: str = None,
        virtual_camera: bool = True
    ) -> bool:
        """
        启动广播

        Args:
            scene_name: 要切换到的场景名称
            virtual_camera: 是否启动虚拟摄像头

        Returns:
            是否启动成功
        """
        print("\n" + "="*60)
        print("🎬 启动直播广播")
        print("="*60)

        try:
            # 1. 切换场景
            if scene_name:
                current = await self.obs.get_current_scene()
                print(f"\n当前场景：{current}")
                if current != scene_name:
                    await self.obs.set_current_scene(scene_name)

            # 2. 启动虚拟摄像头（如果需要）
            if virtual_camera:
                await self.obs.start_virtual_camera()

            # 3. 启动推流
            await self.obs.start_stream()

            self.is_broadcasting = True
            self.broadcast_start_time = datetime.now()

            print(f"\n✅ 直播已启动")
            return True

        except Exception as e:
            print(f"\n❌ 启动直播失败：{e}")
            return False

    async def stop_broadcast(self, virtual_camera: bool = True) -> bool:
        """
        停止广播

        Args:
            virtual_camera: 是否停止虚拟摄像头

        Returns:
            是否停止成功
        """
        print("\n" + "="*60)
        print("🛑 停止直播广播")
        print("="*60)

        try:
            # 1. 停止推流
            await self.obs.stop_stream()

            # 2. 停止虚拟摄像头（如果需要）
            if virtual_camera:
                await self.obs.stop_virtual_camera()

            self.is_broadcasting = False

            if self.broadcast_start_time:
                duration = (datetime.now() - self.broadcast_start_time).total_seconds()
                print(f"\n📊 直播时长：{int(duration)} 秒")

            print(f"\n✅ 直播已停止")
            return True

        except Exception as e:
            print(f"\n❌ 停止直播失败：{e}")
            return False

    async def get_broadcast_status(self) -> Dict:
        """获取广播状态"""
        stream_status = await self.obs.get_stream_status()
        obs_stats = await self.obs.get_obs_stats()

        return {
            "is_broadcasting": self.is_broadcasting,
            "stream_status": stream_status,
            "obs_stats": obs_stats,
            "timestamp": datetime.now().isoformat()
        }

    async def cleanup(self):
        """清理资源"""
        await self.obs.disconnect()


async def test_obs_control():
    """OBS 控制测试"""
    print("\n" + "="*80)
    print("OBS WebSocket 控制测试")
    print("="*80)

    controller = OBSBroadcastController()

    try:
        # 连接
        if not await controller.initialize():
            print("❌ 无法连接到 OBS，请确保：")
            print("   1. OBS Studio 已启动")
            print("   2. WebSocket Server 已启用（Tools → WebSocket Server Settings）")
            print("   3. 地址正确：ws://localhost:4444")
            return

        # 查询状态
        print("\n📊 查询 OBS 当前状态...")
        current_scene = await controller.obs.get_current_scene()
        print(f"   当前场景：{current_scene}")

        stats = await controller.obs.get_obs_stats()
        if stats:
            print(f"   CPU 使用率：{stats.get('cpuUsage', 'N/A'):.1f}%")
            print(f"   内存使用：{stats.get('memoryUsage', 'N/A'):.1f} MB")
            print(f"   平均帧率：{stats.get('averageFrameTime', 'N/A'):.2f} ms")

        # 启动广播
        print("\n▶️  启动 3 秒测试广播...")
        await controller.start_broadcast()

        await asyncio.sleep(3)

        # 停止广播
        await controller.stop_broadcast()

        print("\n✅ 测试完成")

    except Exception as e:
        print(f"\n❌ 测试失败：{e}")

    finally:
        await controller.cleanup()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OBS WebSocket Controller")
    parser.add_argument("--status", action="store_true", help="Get OBS status")
    parser.add_argument("--start-stream", action="store_true", help="Start stream")
    parser.add_argument("--stop-stream", action="store_true", help="Stop stream")
    parser.add_argument("--test", action="store_true", help="Run test")

    args = parser.parse_args()

    if args.test:
        asyncio.run(test_obs_control())
    else:
        print("Usage: python obs-controller.py --test")
        print("       python obs-controller.py --status")
        print("       python obs-controller.py --start-stream")
        print("       python obs-controller.py --stop-stream")
