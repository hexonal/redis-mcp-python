"""Database switching and management tool for Redis."""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from redis.exceptions import RedisError, ResponseError

from ..connection.manager import RedisConnectionManager
from ..config.settings import RedisSettings, RedisMode

logger = logging.getLogger(__name__)


@dataclass 
class DatabaseInfo:
    """Information about a Redis database."""
    db_number: int
    key_count: int
    memory_usage: Optional[int] = None
    expires_count: Optional[int] = None


@dataclass
class DatabaseSwitchResult:
    """Result of database switch operation."""
    success: bool
    previous_db: int
    current_db: int
    error: Optional[str] = None


class DatabaseSwitcher:
    """Tool for switching between Redis databases and managing database state."""
    
    def __init__(self, connection_manager: RedisConnectionManager, settings: RedisSettings):
        """Initialize the database switcher.
        
        Args:
            connection_manager: Redis connection manager
            settings: Redis configuration settings
        """
        self.connection_manager = connection_manager
        self.settings = settings
    
    def switch_database(self, db_number: int) -> DatabaseSwitchResult:
        """Switch to a different Redis database.
        
        Args:
            db_number: Database number to switch to (0-15 typically)
            
        Returns:
            DatabaseSwitchResult with switch operation details
            
        Raises:
            RedisError: If switching fails or not supported
        """
        if self.settings.redis_mode != RedisMode.SINGLE:
            return DatabaseSwitchResult(
                success=False,
                previous_db=self.connection_manager.get_current_database(),
                current_db=self.connection_manager.get_current_database(),
                error=f"Database switching is not supported in {self.settings.redis_mode.value} mode"
            )
        
        if db_number < 0 or db_number > 15:
            return DatabaseSwitchResult(
                success=False,
                previous_db=self.connection_manager.get_current_database(),
                current_db=self.connection_manager.get_current_database(),
                error="Database number must be between 0 and 15"
            )
        
        previous_db = self.connection_manager.get_current_database()
        
        try:
            success = self.connection_manager.switch_database(db_number)
            
            if success:
                logger.info(f"Successfully switched from database {previous_db} to {db_number}")
                return DatabaseSwitchResult(
                    success=True,
                    previous_db=previous_db,
                    current_db=db_number
                )
            else:
                return DatabaseSwitchResult(
                    success=False,
                    previous_db=previous_db,
                    current_db=previous_db,
                    error="Database switch failed for unknown reason"
                )
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to switch to database {db_number}: {error_msg}")
            return DatabaseSwitchResult(
                success=False,
                previous_db=previous_db,
                current_db=previous_db,
                error=error_msg
            )
    
    def get_current_database(self) -> int:
        """Get the current database number.
        
        Returns:
            Current database number
        """
        return self.connection_manager.get_current_database()
    
    def list_databases(self) -> List[DatabaseInfo]:
        """List information about all available databases.
        
        Returns:
            List of DatabaseInfo objects
            
        Note:
            Only works in single instance mode
        """
        if self.settings.redis_mode != RedisMode.SINGLE:
            raise RedisError(f"Database listing is not supported in {self.settings.redis_mode.value} mode")
        
        client = self.connection_manager.get_client()
        current_db = self.get_current_database()
        databases = []
        
        # Redis typically supports databases 0-15
        for db_num in range(16):
            try:
                # Switch to database to check it
                client.execute_command("SELECT", db_num)
                
                # Get database info
                key_count = client.dbsize()
                
                # Try to get additional info (may not be available in all Redis versions)
                memory_usage = None
                expires_count = None
                
                try:
                    # Get memory usage for this database
                    info = client.info("memory")
                    memory_usage = info.get("used_memory", None)
                except Exception:
                    pass
                
                # Count keys with expiration
                try:
                    # This is an approximation - we can't easily count expired keys without scanning
                    expires_count = 0
                except Exception:
                    pass
                
                databases.append(DatabaseInfo(
                    db_number=db_num,
                    key_count=key_count,
                    memory_usage=memory_usage,
                    expires_count=expires_count
                ))
                
                # If database is empty and we've found some databases, we can stop
                if key_count == 0 and db_num > 0 and any(db.key_count > 0 for db in databases[:-1]):
                    # Keep checking a few more to be sure
                    continue
                    
            except ResponseError as e:
                # Database might not exist or be accessible
                if "invalid DB index" in str(e).lower():
                    break  # No more databases available
                else:
                    logger.warning(f"Error accessing database {db_num}: {e}")
                    continue
            except Exception as e:
                logger.warning(f"Error checking database {db_num}: {e}")
                continue
        
        # Switch back to original database
        try:
            client.execute_command("SELECT", current_db)
        except Exception as e:
            logger.error(f"Failed to switch back to original database {current_db}: {e}")
        
        return databases
    
    def get_database_info(self, db_number: Optional[int] = None) -> DatabaseInfo:
        """Get detailed information about a specific database.
        
        Args:
            db_number: Database number to get info for (None for current database)
            
        Returns:
            DatabaseInfo object with database details
        """
        if self.settings.redis_mode != RedisMode.SINGLE:
            raise RedisError(f"Database info is not supported in {self.settings.redis_mode.value} mode")
        
        if db_number is None:
            db_number = self.get_current_database()
        
        client = self.connection_manager.get_client()
        current_db = self.get_current_database()
        
        try:
            # Switch to target database if different
            if db_number != current_db:
                client.execute_command("SELECT", db_number)
            
            # Get basic info
            key_count = client.dbsize()
            
            # Get memory usage
            memory_usage = None
            try:
                info = client.info("memory")
                memory_usage = info.get("used_memory", None)
            except Exception:
                pass
            
            # Count keys with TTL (expensive operation, so we sample)
            expires_count = None
            try:
                if key_count > 0:
                    # Sample some keys to estimate expiring keys
                    cursor = 0
                    sampled_keys = 0
                    expiring_keys = 0
                    max_sample = min(1000, key_count)
                    
                    while sampled_keys < max_sample:
                        cursor, keys = client.scan(cursor=cursor, count=100)
                        for key in keys:
                            sampled_keys += 1
                            if sampled_keys > max_sample:
                                break
                            
                            ttl = client.ttl(key)
                            if ttl > 0:  # Key has expiration
                                expiring_keys += 1
                        
                        if cursor == 0:
                            break
                    
                    # Estimate total expiring keys
                    if sampled_keys > 0:
                        expires_count = int((expiring_keys / sampled_keys) * key_count)
            except Exception as e:
                logger.warning(f"Failed to count expiring keys: {e}")
            
            database_info = DatabaseInfo(
                db_number=db_number,
                key_count=key_count,
                memory_usage=memory_usage,
                expires_count=expires_count
            )
            
            # Switch back to original database if we changed it
            if db_number != current_db:
                client.execute_command("SELECT", current_db)
            
            return database_info
            
        except Exception as e:
            # Make sure we switch back to original database
            try:
                if db_number != current_db:
                    client.execute_command("SELECT", current_db)
            except Exception:
                pass
            
            logger.error(f"Failed to get info for database {db_number}: {e}")
            raise RedisError(f"Failed to get database info: {e}")
    
    def clear_database(self, db_number: Optional[int] = None, confirm: bool = False) -> Dict[str, Any]:
        """Clear all keys in a database (FLUSHDB).
        
        Args:
            db_number: Database number to clear (None for current database)
            confirm: Must be True to actually clear the database
            
        Returns:
            Dictionary with operation result
        """
        if not confirm:
            return {
                "success": False,
                "error": "Confirmation required. Set confirm=True to clear database.",
                "warning": "This operation will delete all keys in the database!"
            }
        
        if self.settings.redis_mode != RedisMode.SINGLE:
            return {
                "success": False,
                "error": f"Database clearing is not supported in {self.settings.redis_mode.value} mode"
            }
        
        if not self.settings.enable_dangerous_commands:
            return {
                "success": False,
                "error": "Database clearing is blocked for safety. Enable dangerous commands to use it."
            }
        
        if db_number is None:
            db_number = self.get_current_database()
        
        client = self.connection_manager.get_client()
        current_db = self.get_current_database()
        
        try:
            # Get key count before clearing
            if db_number != current_db:
                client.execute_command("SELECT", db_number)
            
            keys_before = client.dbsize()
            
            # Clear the database
            client.flushdb()
            
            keys_after = client.dbsize()
            
            # Switch back to original database if we changed it
            if db_number != current_db:
                client.execute_command("SELECT", current_db)
            
            logger.warning(f"Cleared database {db_number}: {keys_before} keys deleted")
            
            return {
                "success": True,
                "database": db_number,
                "keys_deleted": keys_before,
                "keys_remaining": keys_after
            }
            
        except Exception as e:
            # Make sure we switch back to original database
            try:
                if db_number != current_db:
                    client.execute_command("SELECT", current_db)
            except Exception:
                pass
            
            error_msg = str(e)
            logger.error(f"Failed to clear database {db_number}: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_database_summary(self) -> Dict[str, Any]:
        """Get a summary of all databases.
        
        Returns:
            Dictionary with database summary information
        """
        try:
            if self.settings.redis_mode != RedisMode.SINGLE:
                return {
                    "mode": self.settings.redis_mode.value,
                    "current_database": "N/A (cluster/sentinel mode)",
                    "databases": [],
                    "total_databases": 0,
                    "total_keys": 0,
                    "note": "Database switching is not supported in cluster/sentinel mode"
                }
            
            databases = self.list_databases()
            current_db = self.get_current_database()
            
            total_keys = sum(db.key_count for db in databases)
            non_empty_dbs = [db for db in databases if db.key_count > 0]
            
            return {
                "mode": self.settings.redis_mode.value,
                "current_database": current_db,
                "databases": [
                    {
                        "db_number": db.db_number,
                        "key_count": db.key_count,
                        "memory_usage": db.memory_usage,
                        "expires_count": db.expires_count,
                        "is_current": db.db_number == current_db
                    }
                    for db in databases
                ],
                "total_databases": len(databases),
                "non_empty_databases": len(non_empty_dbs),
                "total_keys": total_keys
            }
            
        except Exception as e:
            logger.error(f"Failed to get database summary: {e}")
            return {
                "error": str(e),
                "mode": self.settings.redis_mode.value,
                "current_database": self.get_current_database() if self.settings.redis_mode == RedisMode.SINGLE else "N/A"
            }