# Redis MCP (Model Context Protocol) 服务器

🌐 **Language / 语言**: [English](README.md) | [中文](README_zh.md)

一个基于 FastMCP 构建的强大 Redis MCP 服务器，提供全面的 Redis 管理功能，包括大 key 分析、命令执行和数据库切换，支持单实例、集群和哨兵模式。

## 🚀 功能特性

- **大 key 分析**: 扫描和识别占用大量内存的 key
- **安全命令执行**: 带有安全检查和格式化的 Redis 命令执行
- **数据库管理**: 切换 Redis 数据库并获取数据库信息
- **多模式支持**: 支持单 Redis 实例、集群和哨兵配置
- **安全优先**: 危险命令过滤和可配置的安全设置
- **性能优化**: 管道支持和高效的批量操作
- **全面监控**: 集群健康检查和详细的 Redis 信息

## 🔧 系统要求

- **Python 3.10+** (FastMCP 和 MCP SDK 必需)
- Redis 服务器 (单实例、集群或哨兵)

## 📦 安装方式

### 使用 uvx（推荐）
```bash
# 确保您有 Python 3.10+
python --version

# 使用 uvx 安装
uvx --from git+https://github.com/hexonal/redis-mcp-python.git redis-python-mcp
```

### 使用 pip
```bash
# 确保 Python 3.10+
python --version

pip install git+https://github.com/hexonal/redis-mcp-python.git
```

### 开发环境安装
```bash
git clone https://github.com/hexonal/redis-mcp-python.git
cd redis-mcp-python

# 创建 Python 3.10+ 虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -e .
```

## ⚙️ 配置说明

### Claude Desktop 配置

添加到您的 Claude Desktop 配置中：

```json
{
  "mcpServers": {
    "redis": {
      "command": "uvx",
      "args": [
        "--from", 
        "git+https://github.com/hexonal/redis-mcp-python.git",
        "redis-python-mcp"
      ],
      "env": {
        "REDIS_URL": "redis://localhost:6379",
        "REDIS_MODE": "single",
        "LARGE_KEY_THRESHOLD": "1048576",
        "ENABLE_DANGEROUS_COMMANDS": "false"
      }
    }
  }
}
```

### 环境变量配置

| 变量名 | 说明 | 默认值 | 示例 |
|--------|------|--------|------|
| `REDIS_URL` | 完整的 Redis 连接 URL | None | `redis://user:pass@host:6379` |
| `REDIS_HOST` | Redis 服务器主机 | `localhost` | `redis.example.com` |
| `REDIS_PORT` | Redis 服务器端口 | `6379` | `6380` |
| `REDIS_DB` | Redis 数据库编号 | `0` | `1` |
| `REDIS_PASSWORD` | Redis 密码 | None | `secretpassword` |
| `REDIS_MODE` | 连接模式 | `single` | `single`, `cluster`, `sentinel` |
| `REDIS_CLUSTER_NODES` | 集群节点（逗号分隔） | None | `node1:7000,node2:7001,node3:7002` |
| `REDIS_SENTINEL_HOSTS` | 哨兵主机（逗号分隔） | None | `sent1:26379,sent2:26379,sent3:26379` |
| `REDIS_SENTINEL_SERVICE` | 哨兵服务名称 | `mymaster` | `redis-service` |
| `LARGE_KEY_THRESHOLD` | 大 key 阈值（字节） | `1048576` (1MB) | `2097152` (2MB) |
| `ENABLE_DANGEROUS_COMMANDS` | 允许危险命令 | `false` | `true` |
| `REDIS_MAX_CONNECTIONS` | 连接池最大连接数 | `20` | `50` |

### 连接模式配置

#### 单实例模式
```json
{
  "env": {
    "REDIS_URL": "redis://localhost:6379",
    "REDIS_MODE": "single"
  }
}
```

#### Redis 集群
```json
{
  "env": {
    "REDIS_MODE": "cluster",
    "REDIS_CLUSTER_NODES": "node1:7000,node2:7001,node3:7002",
    "REDIS_PASSWORD": "clusterpassword"
  }
}
```

#### Redis 哨兵
```json
{
  "env": {
    "REDIS_MODE": "sentinel",
    "REDIS_SENTINEL_HOSTS": "sentinel1:26379,sentinel2:26379,sentinel3:26379",
    "REDIS_SENTINEL_SERVICE": "mymaster",
    "REDIS_PASSWORD": "redispassword"
  }
}
```

## 🛠️ 可用的 MCP 工具

### 1. get_redis_info()
获取全面的 Redis 服务器信息和连接状态。

**返回**: 服务器信息、内存使用情况、连接详情和键空间信息。

### 2. analyze_large_keys(pattern="*", limit=None, include_memory_usage=True)
分析 Redis key 以找到占用大量内存的 key。

**参数**:
- `pattern`: 要匹配的 key 模式（默认："*"）
- `limit`: 要扫描的最大 key 数量
- `include_memory_usage`: 包含内存使用分析

**返回**: 包含大 key、内存使用情况和按类型统计的报告。

### 3. execute_command(command, args=[])
执行带有安全检查和格式化的 Redis 命令。

**参数**:
- `command`: 要执行的 Redis 命令
- `args`: 命令参数

**返回**: 带有计时和错误处理的执行结果。

### 4. execute_batch_commands(commands, use_pipeline=False)
批量或管道模式执行多个 Redis 命令。

**参数**:
- `commands`: 要执行的命令列表
- `use_pipeline`: 使用 Redis 管道提高性能

**返回**: 批量执行结果和汇总统计。

### 5. switch_database(db_number)
切换到不同的 Redis 数据库（仅单实例模式）。

**参数**:
- `db_number`: 要切换到的数据库编号（0-15）

**返回**: 切换操作结果。

### 6. get_database_info()
获取所有 Redis 数据库的信息。

**返回**: 包含 key 计数和使用信息的数据库摘要。

### 7. get_key_details(key)
获取特定 Redis key 的详细信息。

**参数**:
- `key`: 要分析的 Redis key

**返回**: 详细的 key 信息，包括类型、大小、TTL 和内容预览。

### 8. get_cluster_info()
获取 Redis 集群信息和健康状态（仅集群模式）。

**返回**: 集群拓扑、节点信息和健康状态。

### 9. clear_database(db_number=None, confirm=False)
清空 Redis 数据库中的所有 key（危险操作）。

**参数**:
- `db_number`: 要清空的数据库（None 为当前数据库）
- `confirm`: 必须为 True 以确认清空操作

**返回**: 清空操作结果。

### 10. get_command_info(command)
获取 Redis 命令的信息，包括安全状态。

**参数**:
- `command`: 要获取信息的命令名称

**返回**: 命令信息和安全状态。

## 🔒 安全功能

### 危险命令保护
默认情况下，危险命令被阻止以防止意外的数据丢失：

- `FLUSHDB`, `FLUSHALL` - 数据库清空
- `SHUTDOWN` - 服务器关闭
- `CONFIG` - 配置更改
- `EVAL`, `EVALSHA` - 任意脚本执行
- `SCRIPT` - 脚本管理
- `DEBUG`, `MONITOR` - 调试命令

### 安全模式 vs 管理模式
- **安全模式**（默认）: 危险命令被阻止
- **管理模式**: 设置 `ENABLE_DANGEROUS_COMMANDS=true` 允许所有命令

## 📊 使用示例

### 查找大 key
```python
# 分析所有 key
result = analyze_large_keys()

# 分析特定模式并限制数量
result = analyze_large_keys(pattern="user:*", limit=10000)

# 快速扫描（不包含内存分析）
result = analyze_large_keys(include_memory_usage=False)
```

### 命令执行
```python
# 安全命令执行
result = execute_command("GET", ["mykey"])

# 批量命令
result = execute_batch_commands([
    "GET key1",
    "SET key2 value2", 
    "INCR counter"
])

# 使用管道提高性能
result = execute_batch_commands(commands, use_pipeline=True)
```

### 数据库管理
```python
# 切换数据库
result = switch_database(1)

# 获取数据库信息
info = get_database_info()

# 获取 key 详情
details = get_key_details("important:key")
```

### 集群操作
```python
# 获取集群状态
cluster_info = get_cluster_info()

# 检查集群健康
health = cluster_info["health_status"]
```

## 🧪 开发指南

### 运行测试
```bash
# 安装开发依赖
pip install -e .[dev]

# 运行所有测试
pytest

# 运行带覆盖率的测试
pytest --cov=redis_mcp

# 运行特定测试文件
pytest tests/unit/test_settings.py -v
```

### 代码质量检查
```bash
# 格式化代码
black .

# 代码检查
ruff check .

# 类型检查
mypy src/redis_mcp
```

### 本地开发
```bash
# 直接启动 MCP 服务器
python -m redis_mcp.server

# 或带调试
REDIS_HOST=localhost REDIS_PORT=6379 python -m redis_mcp.server
```

## 📄 许可证

MIT 许可证 - 详见 LICENSE 文件。

## 🤝 贡献指南

1. Fork 这个仓库
2. 创建功能分支
3. 进行您的更改
4. 为新功能添加测试
5. 确保所有测试通过
6. 提交 Pull Request

## 📞 支持

如有问题和疑问：
- 在 GitHub 上创建 issue
- 查看现有文档
- 参考配置示例

---

使用 ❤️ 和 [FastMCP](https://gofastmcp.com/) 构建