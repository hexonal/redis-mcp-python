"""Large key analysis tool for Redis."""

import logging
import time
from typing import Dict, List, Any, Optional, Union, Iterator
from dataclasses import dataclass
from collections import defaultdict

from redis.exceptions import RedisError, ResponseError

from ..connection.manager import RedisConnectionManager
from ..config.settings import RedisSettings, RedisMode

logger = logging.getLogger(__name__)


@dataclass
class KeyInfo:
    """Information about a Redis key."""
    key: str
    type: str
    size: int
    ttl: Optional[int]
    encoding: Optional[str]
    memory_usage: Optional[int]
    

@dataclass
class LargeKeyReport:
    """Report containing large key analysis results."""
    total_keys_scanned: int
    large_keys_found: int
    total_memory_usage: int
    scan_time_seconds: float
    keys: List[KeyInfo]
    summary_by_type: Dict[str, Dict[str, Any]]
    top_keys_by_size: List[KeyInfo]


class LargeKeyAnalyzer:
    """Analyzer for finding and analyzing large keys in Redis."""
    
    def __init__(self, connection_manager: RedisConnectionManager, settings: RedisSettings):
        """Initialize the large key analyzer.
        
        Args:
            connection_manager: Redis connection manager
            settings: Redis configuration settings
        """
        self.connection_manager = connection_manager
        self.settings = settings
    
    def analyze_large_keys(
        self,
        pattern: str = "*",
        limit: Optional[int] = None,
        include_memory_usage: bool = True
    ) -> LargeKeyReport:
        """Analyze Redis keys to find large ones.
        
        Args:
            pattern: Key pattern to match (default: "*")
            limit: Maximum number of keys to scan (default: from settings)
            include_memory_usage: Whether to include memory usage analysis
            
        Returns:
            LargeKeyReport containing analysis results
        """
        start_time = time.time()
        client = self.connection_manager.get_client()
        
        if limit is None:
            limit = self.settings.max_scan_keys
        
        large_keys = []
        total_scanned = 0
        total_memory = 0
        
        try:
            # Scan keys based on Redis mode
            if self.settings.redis_mode == RedisMode.CLUSTER:
                key_iterator = self._scan_cluster_keys(pattern, limit)
            else:
                key_iterator = self._scan_single_keys(pattern, limit)
            
            # Analyze each key
            for key in key_iterator:
                if total_scanned >= limit:
                    break
                
                try:
                    key_info = self._analyze_key(key, include_memory_usage)
                    total_scanned += 1
                    
                    if key_info.size >= self.settings.large_key_threshold:
                        large_keys.append(key_info)
                        logger.debug(f"Found large key: {key} ({key_info.size} bytes)")
                    
                    if key_info.memory_usage:
                        total_memory += key_info.memory_usage
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze key '{key}': {e}")
                    continue
            
            # Generate summary
            summary_by_type = self._generate_type_summary(large_keys)
            top_keys_by_size = sorted(large_keys, key=lambda x: x.size, reverse=True)[:50]
            
            scan_time = time.time() - start_time
            
            report = LargeKeyReport(
                total_keys_scanned=total_scanned,
                large_keys_found=len(large_keys),
                total_memory_usage=total_memory,
                scan_time_seconds=scan_time,
                keys=large_keys,
                summary_by_type=summary_by_type,
                top_keys_by_size=top_keys_by_size
            )
            
            logger.info(
                f"Large key analysis completed: {len(large_keys)} large keys found "
                f"out of {total_scanned} keys scanned in {scan_time:.2f}s"
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Large key analysis failed: {e}")
            raise RedisError(f"Large key analysis failed: {e}")
    
    def _scan_single_keys(self, pattern: str, limit: int) -> Iterator[str]:
        """Scan keys in single Redis instance mode."""
        client = self.connection_manager.get_client()
        cursor = 0
        scanned = 0
        
        while scanned < limit:
            cursor, keys = client.scan(
                cursor=cursor,
                match=pattern,
                count=self.settings.scan_count
            )
            
            for key in keys:
                if scanned >= limit:
                    break
                yield key
                scanned += 1
            
            if cursor == 0:
                break
    
    def _scan_cluster_keys(self, pattern: str, limit: int) -> Iterator[str]:
        """Scan keys in Redis cluster mode."""
        client = self.connection_manager.get_client()
        scanned = 0
        
        # In cluster mode, scan each node
        try:
            nodes = client.get_nodes()
            for node in nodes:
                if scanned >= limit:
                    break
                
                node_client = node
                cursor = 0
                
                while scanned < limit:
                    cursor, keys = node_client.scan(
                        cursor=cursor,
                        match=pattern,
                        count=self.settings.scan_count
                    )
                    
                    for key in keys:
                        if scanned >= limit:
                            break
                        yield key
                        scanned += 1
                    
                    if cursor == 0:
                        break
        except AttributeError:
            # Fallback for different redis-py-cluster versions
            cursor = 0
            while scanned < limit:
                try:
                    cursor, keys = client.scan(
                        cursor=cursor,
                        match=pattern,
                        count=self.settings.scan_count
                    )
                    
                    for key in keys:
                        if scanned >= limit:
                            break
                        yield key
                        scanned += 1
                    
                    if cursor == 0:
                        break
                except Exception as e:
                    logger.warning(f"Cluster scan error: {e}")
                    break
    
    def _analyze_key(self, key: str, include_memory_usage: bool = True) -> KeyInfo:
        """Analyze a single Redis key.
        
        Args:
            key: Redis key to analyze
            include_memory_usage: Whether to get memory usage info
            
        Returns:
            KeyInfo object with key analysis results
        """
        client = self.connection_manager.get_client()
        
        try:
            # Get key type
            key_type = client.type(key)
            if key_type == "none":
                raise ValueError(f"Key '{key}' does not exist")
            
            # Get TTL
            ttl = client.ttl(key)
            if ttl == -1:
                ttl = None  # Key has no expiration
            
            # Get key size based on type
            size = self._get_key_size(key, key_type)
            
            # Get encoding information
            encoding = None
            try:
                encoding = client.object("encoding", key)
            except Exception:
                # OBJECT command might not be available in all Redis versions/modes
                pass
            
            # Get memory usage if requested and available
            memory_usage = None
            if include_memory_usage:
                try:
                    memory_usage = client.memory_usage(key)
                except Exception:
                    # MEMORY USAGE command might not be available
                    pass
            
            return KeyInfo(
                key=key,
                type=key_type,
                size=size,
                ttl=ttl,
                encoding=encoding,
                memory_usage=memory_usage
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze key '{key}': {e}")
            raise
    
    def _get_key_size(self, key: str, key_type: str) -> int:
        """Get the size of a key based on its type.
        
        Args:
            key: Redis key
            key_type: Type of the key
            
        Returns:
            Size in bytes (approximate)
        """
        client = self.connection_manager.get_client()
        
        try:
            if key_type == "string":
                return client.strlen(key)
            elif key_type == "list":
                return client.llen(key)
            elif key_type == "set":
                return client.scard(key) 
            elif key_type == "zset":
                return client.zcard(key)
            elif key_type == "hash":
                return client.hlen(key)
            elif key_type == "stream":
                return client.xlen(key)
            else:
                # For unknown types, try to get a reasonable estimate
                return len(str(key).encode('utf-8'))
                
        except Exception as e:
            logger.warning(f"Failed to get size for key '{key}' of type '{key_type}': {e}")
            return 0
    
    def _generate_type_summary(self, keys: List[KeyInfo]) -> Dict[str, Dict[str, Any]]:
        """Generate summary statistics by key type.
        
        Args:
            keys: List of KeyInfo objects
            
        Returns:
            Dictionary with statistics by type
        """
        summary = defaultdict(lambda: {
            "count": 0,
            "total_size": 0,
            "avg_size": 0,
            "max_size": 0,
            "min_size": float('inf'),
            "total_memory": 0
        })
        
        for key_info in keys:
            type_stats = summary[key_info.type]
            type_stats["count"] += 1
            type_stats["total_size"] += key_info.size
            type_stats["max_size"] = max(type_stats["max_size"], key_info.size)
            type_stats["min_size"] = min(type_stats["min_size"], key_info.size)
            
            if key_info.memory_usage:
                type_stats["total_memory"] += key_info.memory_usage
        
        # Calculate averages and clean up
        for type_name, stats in summary.items():
            if stats["count"] > 0:
                stats["avg_size"] = stats["total_size"] / stats["count"]
                if stats["min_size"] == float('inf'):
                    stats["min_size"] = 0
        
        return dict(summary)
    
    def get_key_details(self, key: str) -> Dict[str, Any]:
        """Get detailed information about a specific key.
        
        Args:
            key: Redis key to analyze
            
        Returns:
            Dictionary with detailed key information
        """
        client = self.connection_manager.get_client()
        
        try:
            key_info = self._analyze_key(key, include_memory_usage=True)
            
            details = {
                "key": key_info.key,
                "type": key_info.type,
                "size": key_info.size,
                "ttl": key_info.ttl,
                "encoding": key_info.encoding,
                "memory_usage": key_info.memory_usage,
                "is_large": key_info.size >= self.settings.large_key_threshold
            }
            
            # Add type-specific details
            if key_info.type == "string":
                details["value_preview"] = client.get(key)[:100] if key_info.size > 100 else client.get(key)
            elif key_info.type == "hash":
                details["field_count"] = client.hlen(key)
                details["sample_fields"] = list(client.hkeys(key))[:10]
            elif key_info.type == "list":
                details["length"] = client.llen(key) 
                details["sample_values"] = client.lrange(key, 0, 9)
            elif key_info.type == "set":
                details["cardinality"] = client.scard(key)
                details["sample_members"] = list(client.sscan(key, count=10)[1])
            elif key_info.type == "zset":
                details["cardinality"] = client.zcard(key)
                details["sample_members"] = client.zrange(key, 0, 9, withscores=True)
            
            return details
            
        except Exception as e:
            logger.error(f"Failed to get key details for '{key}': {e}")
            raise RedisError(f"Failed to get key details: {e}")