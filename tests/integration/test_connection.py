"""Integration tests for Redis connection management."""

import pytest
from unittest.mock import Mock, patch

from redis_mcp.config.settings import RedisSettings, RedisMode
from redis_mcp.connection.manager import RedisConnectionManager


class TestRedisConnectionIntegration:
    """Integration tests for Redis connection management."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client for testing."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {
            "redis_version": "6.2.0",
            "used_memory": 1024000,
            "connected_clients": 1,
            "role": "master"
        }
        return mock_client
    
    def test_single_connection_success(self, mock_redis_client):
        """Test successful single Redis connection."""
        settings = RedisSettings(redis_mode=RedisMode.SINGLE)
        manager = RedisConnectionManager(settings)
        
        with patch('redis.Redis', return_value=mock_redis_client):
            client = manager.connect()
            
            assert client == mock_redis_client
            assert manager.is_connected()
            mock_redis_client.ping.assert_called_once()
    
    def test_connection_failure_handling(self):
        """Test connection failure handling."""
        settings = RedisSettings(redis_mode=RedisMode.SINGLE)
        manager = RedisConnectionManager(settings)
        
        with patch('redis.Redis') as mock_redis_class:
            mock_redis_class.return_value.ping.side_effect = Exception("Connection failed")
            
            with pytest.raises(Exception) as exc_info:
                manager.connect()
            
            assert "Redis connection failed" in str(exc_info.value)
    
    def test_get_info_success(self, mock_redis_client):
        """Test getting Redis info successfully."""
        settings = RedisSettings(redis_mode=RedisMode.SINGLE)
        manager = RedisConnectionManager(settings)
        
        with patch('redis.Redis', return_value=mock_redis_client):
            manager.connect()
            info = manager.get_info()
            
            assert "connection_mode" in info
            assert "current_database" in info
            assert info["connection_mode"] == "single"
            mock_redis_client.info.assert_called_once()
    
    def test_database_switching_single_mode(self, mock_redis_client):
        """Test database switching in single mode."""
        settings = RedisSettings(redis_mode=RedisMode.SINGLE)
        manager = RedisConnectionManager(settings)
        
        with patch('redis.Redis', return_value=mock_redis_client):
            manager.connect()
            
            # Mock successful SELECT command
            mock_redis_client.execute_command.return_value = "OK"
            
            success = manager.switch_database(1)
            
            assert success is True
            assert manager.get_current_database() == 1
            mock_redis_client.execute_command.assert_called_with("SELECT", 1)
    
    def test_database_switching_cluster_mode_fails(self, mock_redis_client):
        """Test that database switching fails in cluster mode."""
        settings = RedisSettings(redis_mode=RedisMode.CLUSTER)
        manager = RedisConnectionManager(settings)
        
        with pytest.raises(Exception) as exc_info:
            manager.switch_database(1)
        
        assert "single instance mode" in str(exc_info.value).lower()
    
    def test_command_execution(self, mock_redis_client):
        """Test command execution through connection manager."""
        settings = RedisSettings(redis_mode=RedisMode.SINGLE)
        manager = RedisConnectionManager(settings)
        
        with patch('redis.Redis', return_value=mock_redis_client):
            manager.connect()
            
            # Mock command result
            mock_redis_client.execute_command.return_value = "test_result"
            
            result = manager.execute_command("GET", "test_key")
            
            assert result == "test_result"
            mock_redis_client.execute_command.assert_called_with("GET", "test_key")
    
    def test_disconnect_cleanup(self, mock_redis_client):
        """Test proper cleanup on disconnect."""
        settings = RedisSettings(redis_mode=RedisMode.SINGLE)
        manager = RedisConnectionManager(settings)
        
        # Mock connection pool
        mock_pool = Mock()
        mock_redis_client.connection_pool = mock_pool
        
        with patch('redis.Redis', return_value=mock_redis_client):
            manager.connect()
            manager.disconnect()
            
            mock_pool.disconnect.assert_called_once()
            assert not manager.is_connected()
    
    def test_cluster_connection_setup(self):
        """Test cluster connection setup with proper parameters."""
        settings = RedisSettings(
            redis_mode=RedisMode.CLUSTER,
            redis_cluster_nodes=["node1:7000", "node2:7001", "node3:7002"]
        )
        manager = RedisConnectionManager(settings)
        
        mock_cluster_client = Mock()
        mock_cluster_client.ping.return_value = True
        
        with patch('redis.RedisCluster', return_value=mock_cluster_client) as mock_cluster:
            manager.connect()
            
            # Verify cluster client was created with correct startup nodes
            mock_cluster.assert_called_once()
            call_args = mock_cluster.call_args
            startup_nodes = call_args[1]['startup_nodes']
            
            assert len(startup_nodes) == 3
            assert {"host": "node1", "port": 7000} in startup_nodes
            assert {"host": "node2", "port": 7001} in startup_nodes
            assert {"host": "node3", "port": 7002} in startup_nodes