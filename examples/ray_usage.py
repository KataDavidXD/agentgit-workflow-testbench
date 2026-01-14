"""
Ray + Environment Fabric 集成使用示例

本示例展示如何将 Environment Fabric 与 Ray 集成，实现：
1. AOT 预构建环境（工作流预热）
2. 使用 py_executable 在预构建环境中执行 Ray Task
3. 批量执行任务

运行前提：
1. 启动 Environment Fabric API 服务：
   uv run uvicorn src.api:app --host 0.0.0.0 --port 8000

2. 安装 Ray：
   pip install ray

3. 运行本示例：
   python examples/ray_usage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.integrations import EnvFabricClient, RayEnvExecutor, EnvConfig


def example_basic_usage():
    """
    示例 1：基础用法 - 确保环境并获取 Python 路径
    """
    print("=" * 60)
    print("示例 1：基础用法")
    print("=" * 60)
    
    with EnvFabricClient("http://localhost:8000") as client:
        # 确保环境存在，返回 Python 解释器路径
        python_path = client.ensure_env(
            workflow_id="demo-workflow",
            node_id="numpy-node",
            packages=["numpy>=1.24.0"],
        )
        
        print(f"Python 路径: {python_path}")
        
        # 这个路径可以直接用于 Ray 的 py_executable
        print("\n可用于 Ray 的 runtime_env 配置:")
        print(f'runtime_env = {{"py_executable": "{python_path}"}}')


def example_workflow_preheat():
    """
    示例 2：工作流预热 - AOT 批量构建所有节点环境
    """
    print("\n" + "=" * 60)
    print("示例 2：工作流预热 (AOT)")
    print("=" * 60)
    
    # 定义工作流所有节点的环境配置
    node_configs = [
        EnvConfig(
            workflow_id="ml-pipeline",
            node_id="data-loader",
            packages=["pandas>=2.0", "pyarrow"],
        ),
        EnvConfig(
            workflow_id="ml-pipeline",
            node_id="feature-engineer",
            packages=["pandas>=2.0", "numpy>=1.24"],
        ),
        EnvConfig(
            workflow_id="ml-pipeline",
            node_id="model-trainer",
            packages=["scikit-learn>=1.0", "numpy>=1.24"],
        ),
    ]
    
    with RayEnvExecutor("http://localhost:8000") as executor:
        print("🔨 预热工作流环境...")
        
        # 批量预构建所有环境
        python_paths = executor.prepare_workflow(node_configs)
        
        print("✅ 环境准备完成:")
        for env_id, path in python_paths.items():
            print(f"  {env_id}: {path}")


def example_execute_code():
    """
    示例 3：执行代码 - 在预构建环境中运行 Python 代码
    """
    print("\n" + "=" * 60)
    print("示例 3：执行代码")
    print("=" * 60)
    
    with RayEnvExecutor("http://localhost:8000") as executor:
        # 确保环境存在
        executor.ensure_env(
            workflow_id="demo-workflow",
            node_id="numpy-node",
            packages=["numpy"],
        )
        
        # 通过 API 执行代码
        result = executor.execute(
            workflow_id="demo-workflow",
            node_id="numpy-node",
            code="import numpy; print(f'NumPy version: {numpy.__version__}')",
        )
        
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        print(f"returncode: {result.returncode}")


def example_ray_integration():
    """
    示例 4：Ray 集成 - 使用 py_executable 执行 Ray Task
    
    注意：需要安装 ray 包
    """
    print("\n" + "=" * 60)
    print("示例 4：Ray 集成")
    print("=" * 60)
    
    try:
        import ray
    except ImportError:
        print("⚠️  Ray 未安装，跳过此示例")
        print("   安装: pip install ray")
        return
    
    with RayEnvExecutor("http://localhost:8000") as executor:
        # 1. 确保环境存在
        python_path = executor.ensure_env(
            workflow_id="ray-demo",
            node_id="compute-node",
            packages=["numpy"],
        )
        
        print(f"Python 路径: {python_path}")
        
        # 2. 获取 Ray runtime_env 配置
        runtime_env = executor.get_ray_runtime_env(
            workflow_id="ray-demo",
            node_id="compute-node",
        )
        
        print(f"runtime_env: {runtime_env}")
        
        # 3. 定义 Ray Task
        @ray.remote(runtime_env=runtime_env)
        def compute_task():
            import numpy as np
            import sys
            return {
                "python": sys.executable,
                "numpy_version": np.__version__,
                "result": np.random.rand(3).tolist(),
            }
        
        # 4. 初始化 Ray 并执行
        if not ray.is_initialized():
            ray.init()
        
        print("\n🚀 执行 Ray Task...")
        result = ray.get(compute_task.remote())
        
        print(f"执行结果:")
        print(f"  Python: {result['python']}")
        print(f"  NumPy: {result['numpy_version']}")
        print(f"  Result: {result['result']}")


def example_ray_parallel():
    """
    示例 5：Ray 并行执行 - 多节点并行任务
    """
    print("\n" + "=" * 60)
    print("示例 5：Ray 并行执行")
    print("=" * 60)
    
    try:
        import ray
    except ImportError:
        print("⚠️  Ray 未安装，跳过此示例")
        return
    
    with RayEnvExecutor("http://localhost:8000") as executor:
        # 预热多个环境
        configs = [
            EnvConfig("parallel-demo", "worker-1", packages=["numpy"]),
            EnvConfig("parallel-demo", "worker-2", packages=["numpy"]),
            EnvConfig("parallel-demo", "worker-3", packages=["numpy"]),
        ]
        
        print("🔨 预热环境...")
        python_paths = executor.prepare_workflow(configs)
        
        if not ray.is_initialized():
            ray.init()
        
        # 创建并行任务
        @ray.remote
        def worker_task(worker_id: int, python_path: str):
            import subprocess
            result = subprocess.run(
                [python_path, "-c", f"import numpy; print('Worker {worker_id}:', numpy.__version__)"],
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        
        print("\n🚀 并行执行任务...")
        futures = []
        for i, (env_id, path) in enumerate(python_paths.items(), 1):
            futures.append(worker_task.remote(i, path))
        
        results = ray.get(futures)
        
        print("执行结果:")
        for r in results:
            print(f"  {r}")


def main():
    """运行所有示例"""
    print("\n🌟 Environment Fabric + Ray 集成示例 🌟\n")
    
    # 注意：以下示例需要 Environment Fabric API 服务正在运行
    # 启动命令：uv run uvicorn src.api:app --host 0.0.0.0 --port 8000
    
    try:
        example_basic_usage()
        example_workflow_preheat()
        example_execute_code()
        example_ray_integration()
        example_ray_parallel()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请确保 Environment Fabric API 服务正在运行:")
        print("  uv run uvicorn src.api:app --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
