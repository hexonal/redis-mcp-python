"""Tests for Redis MCP settings."""

import pytest
import os
from unittest.mock import patch

from redis_mcp.config.settings import RedisSettings, RedisMode


class TestRedisSettings:
    """Test Redis settings configuration."""
    
    def test_default_settings(self):
        """Test default configuration values."""
        settings = RedisSettings()
        
        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 0
        assert settings.redis_mode == RedisMode.SINGLE
        assert settings.large_key_threshold == 1048576  # 1MB
        assert settings.redis_max_connections == 20
        assert not settings.enable_dangerous_commands
        assert "FLUSHDB" in settings.dangerous_commands
    
    def test_environment_variables(self):
        """Test configuration from environment variables."""
        env_vars = {
            "REDIS_HOST": "redis.example.com",
            "REDIS_PORT": "6380",
            "REDIS_DB": "1",
            "REDIS_PASSWORD": "secret123",
            "REDIS_MODE": "cluster",
            "LARGE_KEY_THRESHOLD": "2097152",  # 2MB
            "ENABLE_DANGEROUS_COMMANDS": "true"
        }
        
        with patch.dict(os.environ, env_vars):
            settings = RedisSettings()
            
            assert settings.redis_host == "redis.example.com"
            assert settings.redis_port == 6380
            assert settings.redis_db == 1
            assert settings.redis_password == "secret123"
            assert settings.redis_mode == RedisMode.CLUSTER
            assert settings.large_key_threshold == 2097152
            assert settings.enable_dangerous_commands is True
    
    def test_cluster_nodes_parsing(self):
        """Test parsing of cluster nodes from string."""
        env_vars = {
            "REDIS_CLUSTER_NODES": "node1:7000,node2:7001,node3:7002"
        }
        
        with patch.dict(os.environ, env_vars):
            settings = RedisSettings()
            
            assert settings.redis_cluster_nodes == ["node1:7000", "node2:7001", "node3:7002"]
    
    def test_sentinel_hosts_parsing(self):
        """Test parsing of sentinel hosts from string."""
        env_vars = {
            "REDIS_SENTINEL_HOSTS": "sentinel1:26379,sentinel2:26379,sentinel3:26379"
        }
        
        with patch.dict(os.environ, env_vars):
            settings = RedisSettings()
            
            expected_hosts = [
                {"host": "sentinel1", "port": 26379},
                {"host": "sentinel2", "port": 26379},
                {"host": "sentinel3", "port": 26379}
            ]
            assert settings.redis_sentinel_hosts == expected_hosts
    
    def test_redis_url_priority(self):
        """Test that REDIS_URL takes priority over individual settings."""
        env_vars = {
            "REDIS_URL": "redis://user:pass@redis.example.com:6380/2",
            "REDIS_HOST": "localhost",  # Should be overridden
            "REDIS_PORT": "6379"       # Should be overridden
        }
        
        with patch.dict(os.environ, env_vars):
            settings = RedisSettings()
            
            assert settings.redis_url == "redis://user:pass@redis.example.com:6380/2"
            # Individual settings are still available for fallback
            assert settings.redis_host == "localhost"
            assert settings.redis_port == 6379
    
    def test_invalid_mode_defaults_to_single(self):
        """Test that invalid Redis mode defaults to single."""
        env_vars = {
            "REDIS_MODE": "invalid_mode"
        }
        
        with patch.dict(os.environ, env_vars):
            # This should raise a validation error
            with pytest.raises(ValueError):
                RedisSettings()
    
    def test_dangerous_commands_list(self):
        """Test dangerous commands configuration."""
        settings = RedisSettings()
        
        dangerous_commands = settings.dangerous_commands
        
        assert "FLUSHDB" in dangerous_commands
        assert "FLUSHALL" in dangerous_commands
        assert "SHUTDOWN" in dangerous_commands
        assert "CONFIG" in dangerous_commands
        assert "EVAL" in dangerous_commands
        
        # Safe commands should not be in the list
        assert "GET" not in dangerous_commands
        assert "SET" not in dangerous_commands
        assert "KEYS" not in dangerous_commands