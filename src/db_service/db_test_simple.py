"""
简单的数据库测试脚本
- 初始化建表
- 写入测试数据
- 查询验证
"""

import time
from src.db_service.connection import get_db, init_db, SessionLocal
from src.db_service.env_repository import EnvOperationRepository
from src.db_service.env_audit import EnvAudit


def main():
    # ------------------------------------------------------------------
    # 1. 初始化数据库（建表）
    # ------------------------------------------------------------------
    print("=" * 50)
    print("1. 初始化数据库...")
    init_db()
    print("   表创建成功！")

    # ------------------------------------------------------------------
    # 2. 获取数据库会话
    # ------------------------------------------------------------------
    db = SessionLocal()
    try:
        # --------------------------------------------------------------
        # 3. 使用 Repository 直接写入数据
        # --------------------------------------------------------------
        print("\n" + "=" * 50)
        print("2. 使用 Repository 写入数据...")

        repo = EnvOperationRepository(db)

        record1 = repo.create(
            workflow_id="wf-test-001",
            node_id="node-001",
            operation="create_env",
            status="success",
            stdout="Environment created",
            exit_code=0,
            duration_ms=150.5,
            metadata={"python_version": "3.11"},
        )
        print(f"   写入记录1: id={record1.id}, operation={record1.operation}")

        record2 = repo.create(
            workflow_id="wf-test-001",
            node_id="node-001",
            operation="add_deps",
            status="failed",
            stderr="Package not found",
            duration_ms=50.0,
            metadata={"packages": ["nonexistent-pkg"]},
        )
        print(f"   写入记录2: id={record2.id}, operation={record2.operation}")


        # --------------------------------------------------------------
        # 4. 使用 EnvAudit 写入数据
        # --------------------------------------------------------------
        print("\n" + "=" * 50)
        print("3. 使用 EnvAudit 写入数据...")

        audit = EnvAudit(
            db=db,
            workflow_id="wf-test-002",
            node_id="node-002",
        )

        # 模拟成功操作
        start_time = audit.start()
        time.sleep(0.2)  # 模拟操作耗时
        audit.success(
            operation="run",
            start_time=start_time,
            stdout="Script executed successfully",
            exit_code=0,
            metadata={"script": "main.py"},
        )
        print("   写入成功操作记录")

        # 模拟失败操作
        start_time = audit.start()
        audit.failed(
            operation="sync",
            start_time=start_time,
            error="Connection timeout",
            metadata={"timeout": 30},
        )
        print("   写入失败操作记录")

        # --------------------------------------------------------------
        # 5. 查询验证
        # --------------------------------------------------------------
        print("\n" + "=" * 50)
        print("4. 查询验证...")

        # 查询所有 wf-test-001 的记录
        records = repo.get_by_workflow_id("wf-test-001")
        print(f"\n   workflow 'wf-test-001' 共有 {len(records)} 条记录:")
        for r in records:
            print(f"   - id={r.id}, op={r.operation}, status={r.status}")

        # 查询失败的记录
        failed = repo.get_failed_operations()
        print(f"\n   失败记录共 {len(failed)} 条:")
        for r in failed:
            print(f"   - id={r.id}, workflow={r.workflow_id}, op={r.operation}")

        print("\n" + "=" * 50)
        print("测试完成！")

    finally:
        db.close()


if __name__ == "__main__":
    main()