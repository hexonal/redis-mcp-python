"""Settings and configuration management for Redis MCP."""

import os
from enum import Enum
from typing import Optional, List, Union, Dict
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class RedisMode(str, Enum):
    """Redis connection mode."""
    SINGLE = "single"
    CLUSTER = "cluster"
    SENTINEL = "sentinel"


class RedisSettings(BaseSettings):
    """Redis MCP configuration settings."""
    
    # Redis connection settings
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection URL (e.g., redis://localhost:6379/0)"
    )
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    
    # Cluster/Sentinel settings
    redis_mode: RedisMode = Field(
        default=RedisMode.SINGLE,
        description="Redis connection mode: single, cluster, or sentinel"
    )
    redis_cluster_nodes: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Comma-separated list of cluster nodes (host:port)"
    )
    redis_sentinel_hosts: Optional[Union[str, List[Dict[str, Union[str, int]]]]] = Field(
        default=None,
        description="Comma-separated list of sentinel hosts (host:port)"
    )
    redis_sentinel_service: str = Field(
        default="mymaster",
        description="Sentinel service name"
    )
    
    # Connection pool settings
    redis_max_connections: int = Field(
        default=20,
        description="Maximum number of connections in the pool"
    )
    redis_retry_on_timeout: bool = Field(
        default=True,
        description="Retry on connection timeout"
    )
    redis_health_check_interval: int = Field(
        default=30,
        description="Health check interval in seconds"
    )
    redis_socket_connect_timeout: float = Field(
        default=5.0,
        description="Socket connection timeout in seconds"
    )
    redis_socket_keepalive: bool = Field(
        default=True,
        description="Enable socket keepalive"
    )
    
    # Large key analysis settings
    large_key_threshold: int = Field(
        default=1048576,  # 1MB
        description="Threshold for considering a key as 'large' (in bytes)"
    )
    scan_count: int = Field(
        default=1000,
        description="Number of keys to scan at once during large key analysis"
    )
    max_scan_keys: int = Field(
        default=100000,
        description="Maximum number of keys to scan in one operation"
    )
    
    # Command execution settings
    dangerous_commands: List[str] = Field(
        default_factory=lambda: [
            "FLUSHDB", "FLUSHALL", "SHUTDOWN", "CONFIG", "EVAL", "EVALSHA",
            "SCRIPT", "DEBUG", "MONITOR", "SYNC", "PSYNC"
        ],
        description="List of dangerous commands to filter out"
    )
    enable_dangerous_commands: bool = Field(
        default=False,
        description="Whether to allow execution of dangerous commands"
    )
    command_timeout: float = Field(
        default=30.0,
        description="Command execution timeout in seconds"
    )
    
    @field_validator("redis_cluster_nodes", mode="before")
    @classmethod
    def parse_cluster_nodes(cls, v):
        """Parse cluster nodes from comma-separated string."""
        if isinstance(v, str) and v:
            return [node.strip() for node in v.split(",")]
        return v
    
    @field_validator("redis_sentinel_hosts", mode="before")
    @classmethod
    def parse_sentinel_hosts(cls, v):
        """Parse sentinel hosts from comma-separated string."""
        if isinstance(v, str) and v:
            return [
                {"host": host.split(":")[0], "port": int(host.split(":")[1])}
                for host in v.split(",")
                if ":" in host
            ]
        return v
    
    model_config = {
        "env_prefix": "",
        "case_sensitive": False
    }