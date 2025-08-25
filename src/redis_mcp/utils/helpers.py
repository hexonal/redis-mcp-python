"""Helper utilities for Redis MCP."""

import json
from typing import Any
from datetime import datetime, timedelta


def format_bytes(bytes_size: int) -> str:
    """Format bytes into human readable format.
    
    Args:
        bytes_size: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if bytes_size == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(bytes_size)
    i = 0
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """Format duration in seconds into human readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2.5s", "1m 30s")
    """
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        return f"{hours}h {remaining_minutes}m"


def safe_json_serialize(obj: Any) -> Any:
    """Safely serialize objects to JSON-compatible format.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON-compatible object
    """
    if obj is None:
        return None
    elif isinstance(obj, (bool, int, float, str)):
        return obj
    elif isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return f"<binary data: {len(obj)} bytes>"
    elif isinstance(obj, (list, tuple)):
        return [safe_json_serialize(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(k): safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, set):
        return list(obj)
    elif hasattr(obj, '__dict__'):
        return safe_json_serialize(obj.__dict__)
    else:
        return str(obj)