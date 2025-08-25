"""Redis MCP Server implementation."""

import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .config.settings import RedisSettings
from .connection.manager import RedisConnectionManager
from .connection.cluster import RedisClusterManager
from .tools.analyzer import LargeKeyAnalyzer
from .tools.executor import CommandExecutor
from .tools.database import DatabaseSwitcher
from .utils.helpers import format_bytes, format_duration, safe_json_serialize

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Redis MCP Server")

# Global instances (will be initialized on first use)
_connection_manager: Optional[RedisConnectionManager] = None
_cluster_manager: Optional[RedisClusterManager] = None
_analyzer: Optional[LargeKeyAnalyzer] = None
_executor: Optional[CommandExecutor] = None
_database_switcher: Optional[DatabaseSwitcher] = None
_settings: Optional[RedisSettings] = None


def get_connection_manager() -> RedisConnectionManager:
    """Get or create Redis connection manager."""
    global _connection_manager, _settings
    
    if _connection_manager is None:
        if _settings is None:
            _settings = RedisSettings()
        _connection_manager = RedisConnectionManager(_settings)
        _connection_manager.connect()
    
    return _connection_manager


def get_tools() -> tuple:
    """Get or create all tool instances."""
    global _cluster_manager, _analyzer, _executor, _database_switcher
    
    connection_manager = get_connection_manager()
    
    if _cluster_manager is None:
        _cluster_manager = RedisClusterManager(connection_manager)
    
    if _analyzer is None:
        _analyzer = LargeKeyAnalyzer(connection_manager, _settings)
    
    if _executor is None:
        _executor = CommandExecutor(connection_manager, _settings)
    
    if _database_switcher is None:
        _database_switcher = DatabaseSwitcher(connection_manager, _settings)
    
    return _cluster_manager, _analyzer, _executor, _database_switcher


# Pydantic models for tool parameters
class AnalyzeLargeKeysParams(BaseModel):
    """Parameters for analyze_large_keys tool."""
    pattern: str = Field(default="*", description="Key pattern to match (e.g., 'user:*')")
    limit: Optional[int] = Field(default=None, description="Maximum keys to scan")
    include_memory_usage: bool = Field(default=True, description="Include memory usage analysis")


class ExecuteCommandParams(BaseModel):
    """Parameters for execute_command tool."""
    command: str = Field(description="Redis command to execute")
    args: List[str] = Field(default_factory=list, description="Command arguments")


class ExecuteBatchCommandsParams(BaseModel):
    """Parameters for execute_batch_commands tool."""
    commands: List[Union[str, List[str]]] = Field(description="List of commands to execute")
    use_pipeline: bool = Field(default=False, description="Use Redis pipeline for better performance")


class SwitchDatabaseParams(BaseModel):
    """Parameters for switch_database tool."""
    db_number: int = Field(description="Database number to switch to (0-15)")


class GetKeyDetailsParams(BaseModel):
    """Parameters for get_key_details tool."""
    key: str = Field(description="Redis key to analyze")


class ClearDatabaseParams(BaseModel):
    """Parameters for clear_database tool."""
    db_number: Optional[int] = Field(default=None, description="Database to clear (current if None)")
    confirm: bool = Field(default=False, description="Must be True to confirm clearing")


# MCP Tools
@mcp.tool()
def get_redis_info() -> Dict[str, Any]:
    """Get Redis server information and connection status."""
    try:
        connection_manager = get_connection_manager()
        info = connection_manager.get_info()
        
        return safe_json_serialize({
            "status": "connected",
            "connection_mode": info.get("connection_mode"),
            "current_database": info.get("current_database"),
            "redis_version": info.get("redis_version"),
            "used_memory": format_bytes(info.get("used_memory", 0)),
            "connected_clients": info.get("connected_clients"),
            "total_commands_processed": info.get("total_commands_processed"),
            "keyspace": info.get("keyspace", {}),
            "server_info": {
                "uptime": format_duration(info.get("uptime_in_seconds", 0)),
                "role": info.get("role"),
                "tcp_port": info.get("tcp_port")
            }
        })
    except Exception as e:
        logger.error(f"Failed to get Redis info: {e}")
        return {"status": "error", "error": str(e)}


@mcp.tool()
def analyze_large_keys(params: AnalyzeLargeKeysParams) -> Dict[str, Any]:
    """Analyze Redis keys to find large ones that may be consuming significant memory."""
    try:
        _, analyzer, _, _ = get_tools()
        
        report = analyzer.analyze_large_keys(
            pattern=params.pattern,
            limit=params.limit,
            include_memory_usage=params.include_memory_usage
        )
        
        # Format the report for JSON serialization
        formatted_keys = []
        for key_info in report.top_keys_by_size:
            formatted_keys.append({
                "key": key_info.key,
                "type": key_info.type,
                "size": key_info.size,
                "size_formatted": format_bytes(key_info.size) if key_info.type == "string" else f"{key_info.size} items",
                "ttl": key_info.ttl,
                "encoding": key_info.encoding,
                "memory_usage": format_bytes(key_info.memory_usage) if key_info.memory_usage else None
            })
        
        return safe_json_serialize({
            "summary": {
                "total_keys_scanned": report.total_keys_scanned,
                "large_keys_found": report.large_keys_found,
                "total_memory_usage": format_bytes(report.total_memory_usage),
                "scan_time": format_duration(report.scan_time_seconds),
                "threshold": format_bytes(_settings.large_key_threshold)
            },
            "top_keys": formatted_keys,
            "summary_by_type": report.summary_by_type,
            "pattern_used": params.pattern
        })
    except Exception as e:
        logger.error(f"Large key analysis failed: {e}")
        return {"error": str(e)}


@mcp.tool()
def execute_command(params: ExecuteCommandParams) -> Dict[str, Any]:
    """Execute a Redis command with safety checks and formatting."""
    try:
        _, _, executor, _ = get_tools()
        
        result = executor.execute_command(params.command, *params.args)
        
        return safe_json_serialize({
            "command": result.command,
            "success": result.success,
            "result": result.result,
            "execution_time": f"{result.execution_time_ms:.2f}ms",
            "error": result.error,
            "warning": result.warning
        })
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return {"error": str(e)}


@mcp.tool()
def execute_batch_commands(params: ExecuteBatchCommandsParams) -> Dict[str, Any]:
    """Execute multiple Redis commands in batch or pipeline mode."""
    try:
        _, _, executor, _ = get_tools()
        
        if params.use_pipeline:
            batch_result = executor.execute_pipeline(params.commands)
        else:
            batch_result = executor.execute_batch_commands(params.commands)
        
        formatted_results = []
        for result in batch_result.results:
            formatted_results.append({
                "command": result.command,
                "success": result.success,
                "result": result.result,
                "execution_time": f"{result.execution_time_ms:.2f}ms",
                "error": result.error,
                "warning": result.warning
            })
        
        return safe_json_serialize({
            "summary": {
                "total_commands": batch_result.total_commands,
                "successful_commands": batch_result.successful_commands,
                "failed_commands": batch_result.failed_commands,
                "total_time": f"{batch_result.total_time_ms:.2f}ms",
                "used_pipeline": params.use_pipeline
            },
            "results": formatted_results
        })
    except Exception as e:
        logger.error(f"Batch command execution failed: {e}")
        return {"error": str(e)}


@mcp.tool()
def switch_database(params: SwitchDatabaseParams) -> Dict[str, Any]:
    """Switch to a different Redis database (single instance mode only)."""
    try:
        _, _, _, database_switcher = get_tools()
        
        result = database_switcher.switch_database(params.db_number)
        
        return safe_json_serialize({
            "success": result.success,
            "previous_database": result.previous_db,
            "current_database": result.current_db,
            "error": result.error
        })
    except Exception as e:
        logger.error(f"Database switch failed: {e}")
        return {"error": str(e)}


@mcp.tool()
def get_database_info() -> Dict[str, Any]:
    """Get information about all Redis databases."""
    try:
        _, _, _, database_switcher = get_tools()
        
        summary = database_switcher.get_database_summary()
        
        return safe_json_serialize(summary)
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {"error": str(e)}


@mcp.tool()
def get_key_details(params: GetKeyDetailsParams) -> Dict[str, Any]:
    """Get detailed information about a specific Redis key."""
    try:
        _, analyzer, _, _ = get_tools()
        
        details = analyzer.get_key_details(params.key)
        
        # Format sizes for better readability
        if details.get("size") is not None:
            if details["type"] == "string":
                details["size_formatted"] = format_bytes(details["size"])
            else:
                details["size_formatted"] = f"{details['size']} items"
        
        if details.get("memory_usage") is not None:
            details["memory_usage_formatted"] = format_bytes(details["memory_usage"])
        
        return safe_json_serialize(details)
    except Exception as e:
        logger.error(f"Failed to get key details: {e}")
        return {"error": str(e)}


@mcp.tool()
def get_cluster_info() -> Dict[str, Any]:
    """Get Redis cluster information (cluster mode only)."""
    try:
        cluster_manager, _, _, _ = get_tools()
        
        info = cluster_manager.get_cluster_info()
        health = cluster_manager.check_cluster_health()
        
        return safe_json_serialize({
            "cluster_info": info,
            "health_status": health
        })
    except Exception as e:
        logger.error(f"Failed to get cluster info: {e}")
        return {"error": str(e)}


@mcp.tool()
def clear_database(params: ClearDatabaseParams) -> Dict[str, Any]:
    """Clear all keys in a Redis database (DANGEROUS OPERATION)."""
    try:
        _, _, _, database_switcher = get_tools()
        
        result = database_switcher.clear_database(
            db_number=params.db_number,
            confirm=params.confirm
        )
        
        return safe_json_serialize(result)
    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        return {"error": str(e)}


@mcp.tool()
def get_command_info(command: str) -> Dict[str, Any]:
    """Get information about a Redis command, including whether it's dangerous or blocked."""
    try:
        _, _, executor, _ = get_tools()
        
        info = executor.get_command_info(command)
        dangerous_commands = executor.get_dangerous_commands()
        
        return safe_json_serialize({
            "command_info": info,
            "dangerous_commands_info": dangerous_commands
        })
    except Exception as e:
        logger.error(f"Failed to get command info: {e}")
        return {"error": str(e)}


def main():
    """Main entry point for the MCP server."""
    try:
        logger.info("Starting Redis MCP Server...")
        
        # Initialize settings
        global _settings
        _settings = RedisSettings()
        
        logger.info(f"Redis Mode: {_settings.redis_mode}")
        logger.info(f"Large Key Threshold: {format_bytes(_settings.large_key_threshold)}")
        logger.info(f"Dangerous Commands Enabled: {_settings.enable_dangerous_commands}")
        
        # Test connection
        connection_manager = get_connection_manager()
        logger.info("Redis connection established successfully")
        
        # Run the MCP server
        mcp.run()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if _connection_manager:
            _connection_manager.disconnect()
            logger.info("Redis connection closed")


if __name__ == "__main__":
    main()