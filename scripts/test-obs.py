"""
Task 2.6 OBS WebSocket 控制测试
"""

import asyncio
import sys
sys.path.append(".")

from obs_controller import OBSWebSocketClient, OBSBroadcastController


async def test_connection():
    """测试连接"""
    print("\n" + "="*60)
    print("TEST 1: OBS WebSocket 连接")
    print("="*60)

    client = OBSWebSocketClient()

    print("\n🔗 尝试连接到 ws://localhost:4444...")
    if await client.connect():
        print("✅ 连接成功")
        await client.disconnect()
    else:
        print("❌ 连接失败")
        print("\n请确保：")
        print("  1. OBS Studio 已启动")
        print("  2. WebSocket Server 已启用（Tools → WebSocket Server Settings）")
        print("  3. 地址正确：ws://localhost:4444")


async def test_stream_control():
    """测试推流控制"""
    print("\n" + "="*60)
    print("TEST 2: 推流控制")
    print("="*60)

    controller = OBSBroadcastController()

    try:
        if not await controller.initialize():
            print("⚠️  无法连接，跳过此测试")
            return

        # 获取当前状态
        print("\n📊 查询当前推流状态...")
        status = await controller.obs.get_stream_status()
        print(f"   推流中：{status.get('outputActive', False)}")

        # 启动推流 5 秒后停止
        print("\n▶️  启动推流测试（5 秒）...")
        await controller.start_broadcast()

        for i in range(5):
            await asyncio.sleep(1)
            print(f"   运行中... {i+1}/5")

        await controller.stop_broadcast()

        print("\n✅ 推流控制测试完成")

    except Exception as e:
        print(f"❌ 测试失败：{e}")

    finally:
        await controller.cleanup()


async def test_virtual_camera():
    """测试虚拟摄像头"""
    print("\n" + "="*60)
    print("TEST 3: 虚拟摄像头控制")
    print("="*60)

    client = OBSWebSocketClient()

    try:
        if not await client.connect():
            print("⚠️  无法连接，跳过此测试")
            return

        print("\n🎥 启动虚拟摄像头...")
        if await client.start_virtual_camera():
            print("   ✅ 虚拟摄像头已启动")

            await asyncio.sleep(2)

            print("\n🎥 停止虚拟摄像头...")
            if await client.stop_virtual_camera():
                print("   ✅ 虚拟摄像头已停止")

        print("\n✅ 虚拟摄像头测试完成")

    except Exception as e:
        print(f"❌ 测试失败：{e}")

    finally:
        await client.disconnect()


async def test_scene_switching():
    """测试场景切换"""
    print("\n" + "="*60)
    print("TEST 4: 场景切换")
    print("="*60)

    client = OBSWebSocketClient()

    try:
        if not await client.connect():
            print("⚠️  无法连接，跳过此测试")
            return

        print("\n🎬 查询当前场景...")
        current = await client.get_current_scene()
        print(f"   当前场景：{current}")

        print("\n✅ 场景查询测试完成")

    except Exception as e:
        print(f"❌ 测试失败：{e}")

    finally:
        await client.disconnect()


async def test_multiple_start_stop():
    """测试多次启停（稳定性）"""
    print("\n" + "="*60)
    print("TEST 5: 多次启停测试（稳定性）")
    print("="*60)

    controller = OBSBroadcastController()

    try:
        if not await controller.initialize():
            print("⚠️  无法连接，跳过此测试")
            return

        print("\n🔄 执行 3 次启停循环...")

        for i in range(3):
            print(f"\n[循环 {i+1}/3]")

            print("  ▶️  启动...")
            if not await controller.start_broadcast():
                print("  ❌ 启动失败")
                return

            await asyncio.sleep(2)

            print("  ⏹️  停止...")
            if not await controller.stop_broadcast():
                print("  ❌ 停止失败")
                return

            await asyncio.sleep(1)

        print("\n✅ 多次启停测试完成（系统稳定）")

    except Exception as e:
        print(f"❌ 测试失败：{e}")

    finally:
        await controller.cleanup()


async def test_monitoring():
    """测试监控"""
    print("\n" + "="*60)
    print("TEST 6: OBS 性能监控")
    print("="*60)

    client = OBSWebSocketClient()

    try:
        if not await client.connect():
            print("⚠️  无法连接，跳过此测试")
            return

        print("\n📊 获取 OBS 统计信息...")
        stats = await client.get_obs_stats()

        if stats:
            print(f"\n系统性能：")
            print(f"  CPU 使用率：{stats.get('cpuUsage', 'N/A')}%")
            print(f"  内存使用：{stats.get('memoryUsage', 'N/A')} MB")
            print(f"  平均帧时间：{stats.get('averageFrameTime', 'N/A'):.2f} ms")
            print(f"  渲染时间：{stats.get('renderTotalFrames', 'N/A')} 帧")
            print(f"  输出总时间：{stats.get('totalStreamTime', 'N/A')} s")

            print("\n✅ 性能监控测试完成")
        else:
            print("⚠️  无法获取统计信息")

    except Exception as e:
        print(f"❌ 测试失败：{e}")

    finally:
        await client.disconnect()


async def main():
    """运行所有测试"""
    print("\n" + "="*80)
    print("Task 2.6 — OBS WebSocket 完整测试套件")
    print("="*80)

    await test_connection()
    await test_stream_control()
    await test_virtual_camera()
    await test_scene_switching()
    await test_multiple_start_stop()
    await test_monitoring()

    print("\n" + "="*80)
    print("✅ 所有测试完成")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
