"""Test configuration and fixtures for Redis MCP tests."""

import pytest
from unittest.mock import Mock
import os

from redis_mcp.config.settings import RedisSettings, RedisMode
from redis_mcp.connection.manager import RedisConnectionManager


@pytest.fixture
def test_settings():
    """Provide test Redis settings."""
    return RedisSettings(
        redis_host="localhost",
        redis_port=6379,
        redis_db=0,
        redis_mode=RedisMode.SINGLE,
        large_key_threshold=1000,  # Smaller threshold for testing
        enable_dangerous_commands=False
    )


@pytest.fixture
def cluster_settings():
    """Provide test Redis cluster settings."""
    return RedisSettings(
        redis_mode=RedisMode.CLUSTER,
        redis_cluster_nodes=["node1:7000", "node2:7001", "node3:7002"],
        large_key_threshold=1000
    )


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with common methods."""
    mock_client = Mock()
    
    # Mock common Redis responses
    mock_client.ping.return_value = True
    mock_client.info.return_value = {
        "redis_version": "6.2.0",
        "used_memory": 1024000,
        "connected_clients": 1,
        "total_commands_processed": 1000,
        "role": "master",
        "tcp_port": 6379,
        "uptime_in_seconds": 3600,
        "keyspace": {"db0": {"keys": 10, "expires": 2}}
    }
    mock_client.dbsize.return_value = 10
    mock_client.execute_command.return_value = "OK"
    mock_client.type.return_value = "string"
    mock_client.ttl.return_value = -1
    mock_client.strlen.return_value = 100
    mock_client.scan.return_value = (0, ["key1", "key2", "key3"])
    mock_client.memory_usage.return_value = 128
    
    return mock_client


@pytest.fixture
def connection_manager(test_settings, mock_redis_client):
    """Provide a connection manager with mocked Redis client."""
    manager = RedisConnectionManager(test_settings)
    manager._client = mock_redis_client
    return manager


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before and after each test."""
    # Store original environment
    original_env = dict(os.environ)
    
    # Clean Redis-related environment variables
    redis_env_vars = [
        "REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD",
        "REDIS_MODE", "REDIS_CLUSTER_NODES", "REDIS_SENTINEL_HOSTS",
        "LARGE_KEY_THRESHOLD", "ENABLE_DANGEROUS_COMMANDS"
    ]
    
    for var in redis_env_vars:
        os.environ.pop(var, None)
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def sample_large_keys():
    """Provide sample large key data for testing."""
    return [
        {"key": "large_string", "type": "string", "size": 2000, "ttl": None},
        {"key": "large_list", "type": "list", "size": 1500, "ttl": 3600},
        {"key": "large_hash", "type": "hash", "size": 5000, "ttl": None},
        {"key": "small_key", "type": "string", "size": 100, "ttl": None}  # Below threshold
    ]


@pytest.fixture 
def sample_redis_commands():
    """Provide sample Redis commands for testing."""
    return [
        "GET test_key",
        "SET test_key test_value", 
        "INCR counter",
        "LPUSH mylist item1",
        "SADD myset member1"
    ]


@pytest.fixture
def dangerous_commands():
    """Provide list of dangerous Redis commands."""
    return [
        "FLUSHDB",
        "FLUSHALL", 
        "SHUTDOWN",
        "CONFIG SET",
        "EVAL 'redis.call(\"flushall\")' 0"
    ]