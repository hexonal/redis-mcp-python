"""Redis command execution tool with safety checks and formatting."""

import logging
import time
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from redis.exceptions import RedisError, ResponseError, TimeoutError

from ..connection.manager import RedisConnectionManager
from ..config.settings import RedisSettings

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a Redis command execution."""
    command: str
    success: bool
    result: Any
    execution_time_ms: float
    error: Optional[str] = None
    warning: Optional[str] = None


@dataclass
class BatchCommandResult:
    """Result of batch command execution."""
    total_commands: int
    successful_commands: int
    failed_commands: int
    total_time_ms: float
    results: List[CommandResult]


class CommandExecutor:
    """Safe Redis command executor with filtering and formatting."""
    
    def __init__(self, connection_manager: RedisConnectionManager, settings: RedisSettings):
        """Initialize the command executor.
        
        Args:
            connection_manager: Redis connection manager
            settings: Redis configuration settings
        """
        self.connection_manager = connection_manager
        self.settings = settings
    
    def execute_command(self, command: str, *args, **kwargs) -> CommandResult:
        """Execute a single Redis command with safety checks.
        
        Args:
            command: Redis command to execute
            *args: Command arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            CommandResult with execution details
        """
        full_command = f"{command} {' '.join(map(str, args))}"
        start_time = time.time()
        
        try:
            # Check if command is dangerous
            if self._is_dangerous_command(command):
                if not self.settings.enable_dangerous_commands:
                    return CommandResult(
                        command=full_command,
                        success=False,
                        result=None,
                        execution_time_ms=0,
                        error=f"Command '{command}' is blocked for safety. "
                               f"Enable dangerous commands to use it."
                    )
                else:
                    warning = f"Warning: Executing dangerous command '{command}'"
                    logger.warning(warning)
            
            client = self.connection_manager.get_client()
            
            # Execute command with timeout
            result = client.execute_command(command, *args, **kwargs)
            execution_time = (time.time() - start_time) * 1000
            
            # Format result for better readability
            formatted_result = self._format_result(result, command)
            
            logger.info(f"Executed command: {full_command} ({execution_time:.2f}ms)")
            
            return CommandResult(
                command=full_command,
                success=True,
                result=formatted_result,
                execution_time_ms=execution_time,
                warning=warning if self._is_dangerous_command(command) else None
            )
            
        except TimeoutError as e:
            error_msg = f"Command timed out after {self.settings.command_timeout}s"
            logger.error(f"Command timeout: {full_command} - {error_msg}")
            return CommandResult(
                command=full_command,
                success=False,
                result=None,
                execution_time_ms=(time.time() - start_time) * 1000,
                error=error_msg
            )
            
        except (RedisError, ResponseError) as e:
            error_msg = str(e)
            logger.error(f"Redis error executing {full_command}: {error_msg}")
            return CommandResult(
                command=full_command,
                success=False,
                result=None,
                execution_time_ms=(time.time() - start_time) * 1000,
                error=error_msg
            )
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error executing {full_command}: {error_msg}")
            return CommandResult(
                command=full_command,
                success=False,
                result=None,
                execution_time_ms=(time.time() - start_time) * 1000,
                error=error_msg
            )
    
    def execute_batch_commands(self, commands: List[Union[str, List[str]]]) -> BatchCommandResult:
        """Execute multiple Redis commands.
        
        Args:
            commands: List of commands. Each command can be:
                     - A string: "GET key"
                     - A list: ["GET", "key"]
                     
        Returns:
            BatchCommandResult with execution details
        """
        start_time = time.time()
        results = []
        successful = 0
        
        for cmd in commands:
            if isinstance(cmd, str):
                # Parse string command
                parts = cmd.split()
                if not parts:
                    continue
                command, args = parts[0], parts[1:]
            elif isinstance(cmd, list) and cmd:
                command, args = cmd[0], cmd[1:]
            else:
                continue
            
            result = self.execute_command(command, *args)
            results.append(result)
            
            if result.success:
                successful += 1
        
        total_time = (time.time() - start_time) * 1000
        
        return BatchCommandResult(
            total_commands=len(results),
            successful_commands=successful,
            failed_commands=len(results) - successful,
            total_time_ms=total_time,
            results=results
        )
    
    def execute_pipeline(self, commands: List[Union[str, List[str]]]) -> BatchCommandResult:
        """Execute commands using Redis pipeline for better performance.
        
        Args:
            commands: List of commands to execute in pipeline
            
        Returns:
            BatchCommandResult with execution details
        """
        start_time = time.time()
        client = self.connection_manager.get_client()
        
        # Check for dangerous commands first
        for cmd in commands:
            if isinstance(cmd, str):
                command_name = cmd.split()[0] if cmd.split() else ""
            elif isinstance(cmd, list) and cmd:
                command_name = cmd[0]
            else:
                continue
            
            if self._is_dangerous_command(command_name) and not self.settings.enable_dangerous_commands:
                return BatchCommandResult(
                    total_commands=len(commands),
                    successful_commands=0,
                    failed_commands=len(commands),
                    total_time_ms=0,
                    results=[CommandResult(
                        command=str(cmd),
                        success=False,
                        result=None,
                        execution_time_ms=0,
                        error=f"Pipeline contains dangerous command '{command_name}'"
                    ) for cmd in commands]
                )
        
        try:
            pipeline = client.pipeline()
            
            # Add commands to pipeline
            for cmd in commands:
                if isinstance(cmd, str):
                    parts = cmd.split()
                    if parts:
                        pipeline.execute_command(parts[0], *parts[1:])
                elif isinstance(cmd, list) and cmd:
                    pipeline.execute_command(cmd[0], *cmd[1:])
            
            # Execute pipeline
            results = pipeline.execute()
            execution_time = (time.time() - start_time) * 1000
            
            # Format results
            command_results = []
            for i, (cmd, result) in enumerate(zip(commands, results)):
                formatted_result = self._format_result(result, str(cmd))
                command_results.append(CommandResult(
                    command=str(cmd),
                    success=True,
                    result=formatted_result,
                    execution_time_ms=execution_time / len(commands)  # Average time per command
                ))
            
            logger.info(f"Executed pipeline with {len(commands)} commands ({execution_time:.2f}ms)")
            
            return BatchCommandResult(
                total_commands=len(command_results),
                successful_commands=len(command_results),
                failed_commands=0,
                total_time_ms=execution_time,
                results=command_results
            )
            
        except Exception as e:
            error_msg = f"Pipeline execution failed: {str(e)}"
            logger.error(error_msg)
            
            return BatchCommandResult(
                total_commands=len(commands),
                successful_commands=0,
                failed_commands=len(commands),
                total_time_ms=(time.time() - start_time) * 1000,
                results=[CommandResult(
                    command=str(cmd),
                    success=False,
                    result=None,
                    execution_time_ms=0,
                    error=error_msg
                ) for cmd in commands]
            )
    
    def _is_dangerous_command(self, command: str) -> bool:
        """Check if a command is considered dangerous.
        
        Args:
            command: Command name to check
            
        Returns:
            True if command is dangerous
        """
        return command.upper() in [cmd.upper() for cmd in self.settings.dangerous_commands]
    
    def _format_result(self, result: Any, command: str) -> Any:
        """Format command result for better readability.
        
        Args:
            result: Raw command result
            command: Command that produced the result
            
        Returns:
            Formatted result
        """
        if result is None:
            return None
        
        command_upper = command.upper().split()[0] if command else ""
        
        # Handle different result types
        if isinstance(result, bytes):
            try:
                return result.decode('utf-8')
            except UnicodeDecodeError:
                return f"<binary data: {len(result)} bytes>"
        
        elif isinstance(result, list):
            # Format list results
            if command_upper in ["KEYS", "SCAN"]:
                return result  # Keep as is for key lists
            elif len(result) > 100:
                return {
                    "total_items": len(result),
                    "sample_items": result[:10],
                    "truncated": True
                }
            else:
                return result
        
        elif isinstance(result, dict):
            # Format dictionary results (like INFO command)
            if len(result) > 50:
                return {
                    "total_fields": len(result),
                    "sample_fields": dict(list(result.items())[:10]),
                    "truncated": True
                }
            else:
                return result
        
        elif isinstance(result, str) and len(result) > 1000:
            # Truncate very long strings
            return {
                "length": len(result),
                "preview": result[:500] + "...",
                "truncated": True
            }
        
        return result
    
    def get_command_info(self, command: str) -> Dict[str, Any]:
        """Get information about a Redis command.
        
        Args:
            command: Command name to get info for
            
        Returns:
            Dictionary with command information
        """
        client = self.connection_manager.get_client()
        
        try:
            # Get command info from Redis
            command_info = client.command_info(command)
            
            return {
                "command": command,
                "exists": command in command_info,
                "is_dangerous": self._is_dangerous_command(command),
                "blocked": self._is_dangerous_command(command) and not self.settings.enable_dangerous_commands,
                "info": command_info.get(command, {}) if command in command_info else None
            }
            
        except Exception as e:
            return {
                "command": command,
                "exists": None,
                "is_dangerous": self._is_dangerous_command(command),
                "blocked": self._is_dangerous_command(command) and not self.settings.enable_dangerous_commands,
                "error": str(e)
            }
    
    def get_dangerous_commands(self) -> Dict[str, Any]:
        """Get list of dangerous commands and their status.
        
        Returns:
            Dictionary with dangerous commands information
        """
        return {
            "dangerous_commands": self.settings.dangerous_commands,
            "enabled": self.settings.enable_dangerous_commands,
            "blocked_count": len(self.settings.dangerous_commands) if not self.settings.enable_dangerous_commands else 0
        }