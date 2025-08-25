"""Redis connection manager for single instance, cluster, and sentinel modes."""

import logging
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlparse

import redis
from redis.sentinel import Sentinel
from redis.exceptions import (
    ConnectionError,
    TimeoutError,
    RedisError,
    ResponseError
)

from ..config.settings import RedisSettings, RedisMode

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """Manages Redis connections for single, cluster, and sentinel modes."""
    
    def __init__(self, settings: RedisSettings):
        """Initialize the connection manager.
        
        Args:
            settings: Redis configuration settings
        """
        self.settings = settings
        self._client: Optional[Union[redis.Redis, redis.RedisCluster]] = None
        self._sentinel: Optional[Sentinel] = None
        self._current_db: int = settings.redis_db
        
    def connect(self) -> Union[redis.Redis, redis.RedisCluster]:
        """Establish Redis connection based on configuration.
        
        Returns:
            Redis client instance
            
        Raises:
            ConnectionError: If connection fails
        """
        try:
            if self.settings.redis_mode == RedisMode.SINGLE:
                self._client = self._create_single_connection()
            elif self.settings.redis_mode == RedisMode.CLUSTER:
                self._client = self._create_cluster_connection()
            elif self.settings.redis_mode == RedisMode.SENTINEL:
                self._client = self._create_sentinel_connection()
            else:
                raise ValueError(f"Unsupported Redis mode: {self.settings.redis_mode}")
                
            # Test connection
            self._client.ping()
            logger.info(f"Successfully connected to Redis in {self.settings.redis_mode} mode")
            
            return self._client
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ConnectionError(f"Redis connection failed: {e}")
    
    def _create_single_connection(self) -> redis.Redis:
        """Create single Redis instance connection."""
        connection_params = self._get_base_connection_params()
        
        if self.settings.redis_url:
            # Parse URL for connection
            parsed_url = urlparse(self.settings.redis_url)
            connection_params.update({
                "host": parsed_url.hostname or self.settings.redis_host,
                "port": parsed_url.port or self.settings.redis_port,
                "db": int(parsed_url.path.lstrip("/") or self.settings.redis_db),
                "password": parsed_url.password or self.settings.redis_password,
            })
        else:
            connection_params.update({
                "host": self.settings.redis_host,
                "port": self.settings.redis_port,
                "db": self.settings.redis_db,
                "password": self.settings.redis_password,
            })
        
        return redis.Redis(**connection_params)
    
    def _create_cluster_connection(self) -> redis.RedisCluster:
        """Create Redis cluster connection."""
        if not self.settings.redis_cluster_nodes:
            raise ValueError("Cluster nodes must be specified for cluster mode")
        
        startup_nodes = []
        for node in self.settings.redis_cluster_nodes:
            if isinstance(node, str) and ":" in node:
                host, port = node.split(":", 1)
                startup_nodes.append({"host": host, "port": int(port)})
        
        if not startup_nodes:
            raise ValueError("No valid cluster nodes found")
        
        connection_params = self._get_base_connection_params()
        # Remove db parameter as it's not supported in cluster mode
        connection_params.pop("db", None)
        
        return redis.RedisCluster(
            startup_nodes=startup_nodes,
            password=self.settings.redis_password,
            **connection_params
        )
    
    def _create_sentinel_connection(self) -> redis.Redis:
        """Create Redis sentinel connection."""
        if not self.settings.redis_sentinel_hosts:
            raise ValueError("Sentinel hosts must be specified for sentinel mode")
        
        sentinels = self.settings.redis_sentinel_hosts
        if isinstance(sentinels, str):
            # Parse comma-separated sentinel hosts
            sentinel_list = []
            for host in sentinels.split(","):
                if ":" in host:
                    h, p = host.split(":", 1)
                    sentinel_list.append((h.strip(), int(p)))
            sentinels = sentinel_list
        
        self._sentinel = Sentinel(
            sentinels,
            socket_timeout=self.settings.redis_socket_connect_timeout,
            password=self.settings.redis_password,
        )
        
        connection_params = self._get_base_connection_params()
        connection_params.update({
            "db": self.settings.redis_db,
            "password": self.settings.redis_password,
        })
        
        return self._sentinel.master_for(
            self.settings.redis_sentinel_service,
            **connection_params
        )
    
    def _get_base_connection_params(self) -> Dict[str, Any]:
        """Get base connection parameters."""
        return {
            "socket_connect_timeout": self.settings.redis_socket_connect_timeout,
            "socket_keepalive": self.settings.redis_socket_keepalive,
            "health_check_interval": self.settings.redis_health_check_interval,
            "retry_on_timeout": self.settings.redis_retry_on_timeout,
            "decode_responses": True,  # Always decode responses to strings
        }
    
    def get_client(self) -> Union[redis.Redis, redis.RedisCluster]:
        """Get the current Redis client.
        
        Returns:
            Redis client instance
            
        Raises:
            ConnectionError: If not connected
        """
        if self._client is None:
            raise ConnectionError("Not connected to Redis. Call connect() first.")
        return self._client
    
    def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client:
            try:
                if hasattr(self._client, "connection_pool"):
                    self._client.connection_pool.disconnect()
                self._client = None
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        
        if self._sentinel:
            self._sentinel = None
    
    def is_connected(self) -> bool:
        """Check if Redis connection is active.
        
        Returns:
            True if connected and responsive, False otherwise
        """
        if not self._client:
            return False
        
        try:
            self._client.ping()
            return True
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            return False
    
    def get_info(self) -> Dict[str, Any]:
        """Get Redis server information.
        
        Returns:
            Dictionary containing Redis server info
        """
        client = self.get_client()
        
        try:
            info = client.info()
            
            # Add connection mode and current database
            info["connection_mode"] = self.settings.redis_mode.value
            info["current_database"] = self._current_db
            
            # Add cluster-specific info if in cluster mode
            if self.settings.redis_mode == RedisMode.CLUSTER:
                info["cluster_nodes"] = len(self.settings.redis_cluster_nodes or [])
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            raise RedisError(f"Failed to get Redis info: {e}")
    
    def switch_database(self, db: int) -> bool:
        """Switch to a different Redis database.
        
        Args:
            db: Database number to switch to
            
        Returns:
            True if successful, False otherwise
            
        Note:
            Database switching is only supported in single instance mode
        """
        if self.settings.redis_mode != RedisMode.SINGLE:
            raise ResponseError("Database switching is only supported in single instance mode")
        
        client = self.get_client()
        
        try:
            client.execute_command("SELECT", db)
            self._current_db = db
            logger.info(f"Switched to database {db}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch to database {db}: {e}")
            raise ResponseError(f"Failed to switch database: {e}")
    
    def get_current_database(self) -> int:
        """Get the current database number.
        
        Returns:
            Current database number
        """
        return self._current_db
    
    def execute_command(self, *args, **kwargs) -> Any:
        """Execute a Redis command.
        
        Args:
            *args: Command arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Command result
        """
        client = self.get_client()
        
        try:
            return client.execute_command(*args, **kwargs)
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise