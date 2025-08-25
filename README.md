# Redis MCP (Model Context Protocol) Server

🌐 **Language / 语言**: [English](README.md) | [中文](README_zh.md)

A powerful Redis MCP server built with FastMCP that provides comprehensive Redis management capabilities including large key analysis, command execution, and database switching with support for single instance, cluster, and sentinel modes.

## 🚀 Features

- **Large Key Analysis**: Scan and identify large keys that consume significant memory
- **Safe Command Execution**: Execute Redis commands with safety checks and formatting
- **Database Management**: Switch between Redis databases and get database information  
- **Multi-Mode Support**: Works with single Redis instances, clusters, and sentinel configurations
- **Security First**: Dangerous command filtering with configurable safety settings
- **Performance Optimized**: Pipeline support and efficient batch operations
- **Comprehensive Monitoring**: Cluster health checks and detailed Redis information

## 🔧 Requirements

- **Python 3.10+** (Required for FastMCP and MCP SDK)
- Redis server (single instance, cluster, or sentinel)

## 📦 Installation

### Using uvx (recommended)
```bash
# Ensure you have Python 3.10+
python --version

# Install with uvx
uvx --from git+https://github.com/your-username/redis-mcp-python.git redis-python-mcp
```

### Using pip
```bash
# Ensure Python 3.10+
python --version

pip install git+https://github.com/your-username/redis-mcp-python.git
```

### Development Installation
```bash
git clone https://github.com/your-username/redis-mcp-python.git
cd redis-mcp-python

# Create virtual environment with Python 3.10+
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -e .
```

## ⚙️ Configuration

### Claude Desktop Configuration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "redis": {
      "command": "uvx",
      "args": [
        "--from", 
        "git+https://github.com/your-username/redis-mcp-python.git",
        "redis-python-mcp"
      ],
      "env": {
        "REDIS_URL": "redis://localhost:6379/0",
        "REDIS_MODE": "single",
        "LARGE_KEY_THRESHOLD": "1048576",
        "ENABLE_DANGEROUS_COMMANDS": "false"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `REDIS_URL` | Complete Redis connection URL | None | `redis://user:pass@host:6379/0` |
| `REDIS_HOST` | Redis server host | `localhost` | `redis.example.com` |
| `REDIS_PORT` | Redis server port | `6379` | `6380` |
| `REDIS_DB` | Redis database number | `0` | `1` |
| `REDIS_PASSWORD` | Redis password | None | `secretpassword` |
| `REDIS_MODE` | Connection mode | `single` | `single`, `cluster`, `sentinel` |
| `REDIS_CLUSTER_NODES` | Cluster nodes (comma-separated) | None | `node1:7000,node2:7001,node3:7002` |
| `REDIS_SENTINEL_HOSTS` | Sentinel hosts (comma-separated) | None | `sent1:26379,sent2:26379,sent3:26379` |
| `REDIS_SENTINEL_SERVICE` | Sentinel service name | `mymaster` | `redis-service` |
| `LARGE_KEY_THRESHOLD` | Large key threshold in bytes | `1048576` (1MB) | `2097152` (2MB) |
| `ENABLE_DANGEROUS_COMMANDS` | Allow dangerous commands | `false` | `true` |
| `REDIS_MAX_CONNECTIONS` | Max connections in pool | `20` | `50` |

### Connection Modes

#### Single Instance
```json
{
  "env": {
    "REDIS_URL": "redis://localhost:6379/0",
    "REDIS_MODE": "single"
  }
}
```

#### Redis Cluster
```json
{
  "env": {
    "REDIS_MODE": "cluster",
    "REDIS_CLUSTER_NODES": "node1:7000,node2:7001,node3:7002",
    "REDIS_PASSWORD": "clusterpassword"
  }
}
```

#### Redis Sentinel
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

## 🛠️ Available MCP Tools

### 1. get_redis_info()
Get comprehensive Redis server information and connection status.

**Returns**: Server info, memory usage, connection details, and keyspace information.

### 2. analyze_large_keys(pattern="*", limit=None, include_memory_usage=True)
Analyze Redis keys to find large ones consuming significant memory.

**Parameters**:
- `pattern`: Key pattern to match (default: "*")
- `limit`: Maximum keys to scan
- `include_memory_usage`: Include memory usage analysis

**Returns**: Report with large keys, memory usage, and statistics by type.

### 3. execute_command(command, args=[])
Execute a Redis command with safety checks and formatting.

**Parameters**:
- `command`: Redis command to execute
- `args`: Command arguments

**Returns**: Execution result with timing and error handling.

### 4. execute_batch_commands(commands, use_pipeline=False)
Execute multiple Redis commands in batch or pipeline mode.

**Parameters**:
- `commands`: List of commands to execute
- `use_pipeline`: Use Redis pipeline for better performance

**Returns**: Batch execution results with summary statistics.

### 5. switch_database(db_number)
Switch to a different Redis database (single instance mode only).

**Parameters**:
- `db_number`: Database number to switch to (0-15)

**Returns**: Switch operation result.

### 6. get_database_info()
Get information about all Redis databases.

**Returns**: Database summary with key counts and usage information.

### 7. get_key_details(key)
Get detailed information about a specific Redis key.

**Parameters**:
- `key`: Redis key to analyze

**Returns**: Detailed key information including type, size, TTL, and content preview.

### 8. get_cluster_info()
Get Redis cluster information and health status (cluster mode only).

**Returns**: Cluster topology, node information, and health status.

### 9. clear_database(db_number=None, confirm=False)
Clear all keys in a Redis database (DANGEROUS OPERATION).

**Parameters**:
- `db_number`: Database to clear (current if None)
- `confirm`: Must be True to confirm clearing

**Returns**: Clearing operation result.

### 10. get_command_info(command)
Get information about a Redis command, including safety status.

**Parameters**:
- `command`: Command name to get info for

**Returns**: Command information and safety status.

## 🔒 Security Features

### Dangerous Command Protection
By default, dangerous commands are blocked to prevent accidental data loss:

- `FLUSHDB`, `FLUSHALL` - Database clearing
- `SHUTDOWN` - Server shutdown
- `CONFIG` - Configuration changes
- `EVAL`, `EVALSHA` - Arbitrary script execution
- `SCRIPT` - Script management
- `DEBUG`, `MONITOR` - Debugging commands

### Safe Mode vs. Administrative Mode
- **Safe Mode** (default): Dangerous commands are blocked
- **Administrative Mode**: Set `ENABLE_DANGEROUS_COMMANDS=true` to allow all commands

## 📊 Usage Examples

### Finding Large Keys
```python
# Analyze all keys
result = analyze_large_keys()

# Analyze specific pattern with limit
result = analyze_large_keys(pattern="user:*", limit=10000)

# Quick scan without memory analysis
result = analyze_large_keys(include_memory_usage=False)
```

### Command Execution
```python
# Safe command execution
result = execute_command("GET", ["mykey"])

# Batch commands
result = execute_batch_commands([
    "GET key1",
    "SET key2 value2", 
    "INCR counter"
])

# Pipeline for better performance
result = execute_batch_commands(commands, use_pipeline=True)
```

### Database Management
```python
# Switch database
result = switch_database(1)

# Get database info
info = get_database_info()

# Get key details
details = get_key_details("important:key")
```

### Cluster Operations
```python
# Get cluster status
cluster_info = get_cluster_info()

# Check cluster health
health = cluster_info["health_status"]
```

## 🧪 Development

### Running Tests
```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
pytest

# Run with coverage
pytest --cov=redis_mcp

# Run specific test file
pytest tests/unit/test_settings.py -v
```

### Code Quality
```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy src/redis_mcp
```

### Local Development
```bash
# Start the MCP server directly
python -m redis_mcp.server

# Or with debugging
REDIS_HOST=localhost REDIS_PORT=6379 python -m redis_mcp.server
```

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check existing documentation
- Review configuration examples

---

Built with ❤️ using [FastMCP](https://gofastmcp.com/)