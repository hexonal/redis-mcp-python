# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 Python 的 Redis MCP（Model Context Protocol）项目，使用 fastmcp 框架进行开发。

## 开发环境设置

### 依赖管理
```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 或使用 Poetry（如果项目使用 Poetry）
poetry install
```

### 开发工具
```bash
# 代码格式化
black .
ruff format .

# 代码检查
ruff check .
mypy .

# 运行测试
pytest
pytest tests/  # 运行所有测试
pytest tests/test_specific.py  # 运行特定测试文件
pytest -v  # 详细输出
pytest -k "test_name"  # 运行特定测试
```

## FastMCP 框架架构

### 核心组件
- **MCP Server**: 实现 Model Context Protocol 的服务器端
- **Redis Integration**: Redis 数据库连接和操作封装
- **Tool Definitions**: MCP 工具定义和实现
- **Resource Management**: 资源管理和生命周期控制

### 项目结构预期
```
redis-mcp-python/
├── src/                    # 源代码目录
│   ├── redis_mcp/         # 主要包
│   │   ├── server.py      # MCP 服务器实现
│   │   ├── tools/         # 工具定义
│   │   └── redis_client.py # Redis 客户端封装
├── tests/                  # 测试目录
├── pyproject.toml         # Python 项目配置
├── requirements.txt       # 依赖列表
└── README.md             # 项目说明
```

## MCP 开发指南

### 工具开发模式
- 使用 fastmcp 的装饰器定义 MCP 工具
- 每个工具应该有清晰的类型注解
- 实现适当的错误处理和验证

### Redis 操作最佳实践
- 使用连接池管理 Redis 连接
- 实现适当的重试机制
- 处理网络异常和超时
- 支持异步操作（如果使用 asyncio）

## 常用开发命令

### 启动 MCP 服务器
```bash
python -m redis_mcp.server
# 或
uvicorn redis_mcp.server:app --reload  # 如果使用 FastAPI
```

### 调试和开发
```bash
# 启动开发模式
python -m redis_mcp.server --debug

# 检查 MCP 工具定义
python -c "from redis_mcp.server import app; print(app.list_tools())"
```

## 测试策略

### 单元测试
- 使用 pytest 作为测试框架
- 模拟 Redis 连接进行单元测试
- 测试覆盖率要求 > 80%

### 集成测试
- 使用 Docker 容器运行 Redis 实例
- 测试完整的 MCP 工具流程
- 验证错误处理和边界情况

## FastMCP 特定配置

### 环境变量
- `REDIS_URL`: Redis 连接 URL
- `MCP_SERVER_PORT`: MCP 服务器端口
- `LOG_LEVEL`: 日志级别

### 配置文件
项目可能使用 `config.json` 或 `.env` 文件进行配置管理。