# env_operations 表结构说明（README）

本项目使用 `env_operations` 表记录 **对 node-level 环境（env）产生副作用的操作**，用于审计、排错、回放与统计分析。

> 设计原则：**一条记录 = 一次环境操作**  
> 例如：创建环境、安装依赖、运行代码、同步环境、删除环境、清理闲置环境等。

---

## 1. 表信息

- 表名：`env_operations`
- ORM Model：`EnvOperation`
- 主要用途：记录每次对 env 的操作结果与执行输出（stdout/stderr）

> [!IMPORTANT]
> 本项目为主服务的**强制审计依赖**：服务启动时会自动 `init_db()` 建表并校验 `DATABASE_URL` 连接；写入失败会导致对应接口返回 `DB_AUDIT_ERROR`。

---

## 2. 字段定义

| 字段名 | 类型 | 是否必填 | 索引 | 说明 |
|------|------|----------|------|------|
| `id` | `Integer` | ✅ | - | 主键，自增 |
| `workflow_id` | `String(255)` | ✅ | ✅ | 工作流 / graph 执行标识，用于串联同一次工作流内的多次 env 操作 |
| `node_id` | `String(255)` | ✅ | ✅ | 环境标识（对应 env 目录名 / node id） |
| `operation` | `String(50)` | ✅ | ✅ | 操作类型，如 `create_env` / `add_deps` / `run` / `sync` / `cleanup` 等 |
| `status` | `String(20)` | ✅ | ✅ | 操作状态：`success` / `failed` |
| `stdout` | `Text` | ❌ | - | 命令或执行输出（标准输出），通常来自 UV 执行结果 |
| `stderr` | `Text` | ❌ | - | 错误输出（标准错误），失败时一般会填充 |
| `exit_code` | `Integer` | ❌ | - | 外部命令退出码（如 UV 命令），成功一般为 0 |
| `duration_ms` | `Float` | ❌ | - | 执行耗时（毫秒） |
| `metadata` | `JSONB` | ❌ | - | 结构化扩展字段，例如 packages、timeout、python_version、cleanup 参数等 |
| `created_at` | `DateTime(timezone=True)` | ✅（默认填充） | ✅ | 记录创建时间（UTC） |

---

## 3. operation 字段建议取值

以下为推荐的标准操作类型（保持一致性便于统计与筛选）：

- `create_env`：创建环境（uv init + 可选安装依赖）
- `delete_env`：删除环境目录
- `add_deps`：添加依赖（uv add）
- `update_deps`：升级依赖（uv add --upgrade）
- `remove_deps`：移除依赖（uv remove）
- `sync`：同步环境（uv sync）
- `run`：在环境中执行代码（uv run）
- `cleanup`：清理闲置环境（批量删除）

---

## 4. metadata 字段约定（示例）

`metadata` 用于存放和操作相关的结构化信息，常见示例：

### create_env
```json
{
  "python_version": "3.11",
  "packages": ["numpy", "pandas"]
}
