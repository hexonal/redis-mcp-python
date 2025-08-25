"""Redis cluster-specific management utilities."""

import logging
from typing import Dict, List, Any, Optional
from redis.exceptions import RedisError, ResponseError

from .manager import RedisConnectionManager

logger = logging.getLogger(__name__)


class RedisClusterManager:
    """Redis cluster-specific operations and utilities."""
    
    def __init__(self, connection_manager: RedisConnectionManager):
        """Initialize cluster manager.
        
        Args:
            connection_manager: Redis connection manager instance
        """
        self.connection_manager = connection_manager
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get detailed cluster information.
        
        Returns:
            Dictionary containing cluster information
            
        Raises:
            RedisError: If not in cluster mode or operation fails
        """
        client = self.connection_manager.get_client()
        
        try:
            # Get cluster nodes information
            cluster_nodes = client.execute_command("CLUSTER", "NODES")
            cluster_info = client.execute_command("CLUSTER", "INFO")
            
            # Parse cluster nodes
            nodes = []
            for line in cluster_nodes.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 8:
                    node_info = {
                        "id": parts[0],
                        "address": parts[1],
                        "flags": parts[2].split(","),
                        "master_id": parts[3] if parts[3] != "-" else None,
                        "ping_sent": int(parts[4]),
                        "pong_recv": int(parts[5]),
                        "config_epoch": int(parts[6]),
                        "link_state": parts[7],
                        "slots": parts[8:] if len(parts) > 8 else []
                    }
                    nodes.append(node_info)
            
            # Parse cluster info
            info_dict = {}
            for line in cluster_info.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    info_dict[key] = value
            
            return {
                "cluster_info": info_dict,
                "nodes": nodes,
                "total_nodes": len(nodes),
                "master_nodes": len([n for n in nodes if "master" in n["flags"]]),
                "slave_nodes": len([n for n in nodes if "slave" in n["flags"]])
            }
            
        except Exception as e:
            logger.error(f"Failed to get cluster info: {e}")
            raise RedisError(f"Failed to get cluster info: {e}")
    
    def get_cluster_slots(self) -> List[Dict[str, Any]]:
        """Get cluster slot distribution.
        
        Returns:
            List of slot ranges with their assigned nodes
        """
        client = self.connection_manager.get_client()
        
        try:
            slots_info = client.execute_command("CLUSTER", "SLOTS")
            
            slots = []
            for slot_range in slots_info:
                if len(slot_range) >= 3:
                    slot_info = {
                        "start_slot": slot_range[0],
                        "end_slot": slot_range[1],
                        "master": {
                            "host": slot_range[2][0],
                            "port": slot_range[2][1],
                            "id": slot_range[2][2] if len(slot_range[2]) > 2 else None
                        },
                        "replicas": []
                    }
                    
                    # Add replica information
                    for replica in slot_range[3:]:
                        if len(replica) >= 2:
                            slot_info["replicas"].append({
                                "host": replica[0],
                                "port": replica[1],
                                "id": replica[2] if len(replica) > 2 else None
                            })
                    
                    slots.append(slot_info)
            
            return slots
            
        except Exception as e:
            logger.error(f"Failed to get cluster slots: {e}")
            raise RedisError(f"Failed to get cluster slots: {e}")
    
    def get_node_keys_count(self) -> Dict[str, int]:
        """Get key count for each cluster node.
        
        Returns:
            Dictionary mapping node addresses to key counts
        """
        try:
            cluster_info = self.get_cluster_info()
            nodes = cluster_info["nodes"]
            
            key_counts = {}
            
            for node in nodes:
                if "master" in node["flags"]:
                    try:
                        # For each master node, get the key count
                        # This is an approximation using DBSIZE
                        address = node["address"]
                        if address.startswith("@"):
                            continue  # Skip bus port addresses
                        
                        # Note: Getting exact key count per node in a cluster
                        # requires connecting to each node individually
                        # For now, we'll use the cluster info
                        key_counts[address] = 0  # Placeholder
                        
                    except Exception as e:
                        logger.warning(f"Failed to get key count for node {node['address']}: {e}")
                        key_counts[node["address"]] = -1
            
            return key_counts
            
        except Exception as e:
            logger.error(f"Failed to get node key counts: {e}")
            raise RedisError(f"Failed to get node key counts: {e}")
    
    def check_cluster_health(self) -> Dict[str, Any]:
        """Check cluster health status.
        
        Returns:
            Dictionary containing health information
        """
        try:
            cluster_info = self.get_cluster_info()
            cluster_state = cluster_info["cluster_info"].get("cluster_state", "unknown")
            
            health_status = {
                "healthy": cluster_state == "ok",
                "cluster_state": cluster_state,
                "total_nodes": cluster_info["total_nodes"],
                "master_nodes": cluster_info["master_nodes"],
                "slave_nodes": cluster_info["slave_nodes"],
                "issues": []
            }
            
            # Check for common issues
            nodes = cluster_info["nodes"]
            
            # Check for failed nodes
            failed_nodes = [n for n in nodes if "fail" in n["flags"]]
            if failed_nodes:
                health_status["issues"].append({
                    "type": "failed_nodes",
                    "count": len(failed_nodes),
                    "nodes": [n["address"] for n in failed_nodes]
                })
            
            # Check for nodes in handshake state
            handshake_nodes = [n for n in nodes if "handshake" in n["flags"]]
            if handshake_nodes:
                health_status["issues"].append({
                    "type": "handshake_nodes",
                    "count": len(handshake_nodes),
                    "nodes": [n["address"] for n in handshake_nodes]
                })
            
            # Check for masters without slaves
            masters = [n for n in nodes if "master" in n["flags"]]
            masters_without_slaves = []
            for master in masters:
                slaves = [n for n in nodes if n["master_id"] == master["id"]]
                if not slaves:
                    masters_without_slaves.append(master["address"])
            
            if masters_without_slaves:
                health_status["issues"].append({
                    "type": "masters_without_slaves",
                    "count": len(masters_without_slaves),
                    "nodes": masters_without_slaves
                })
            
            return health_status
            
        except Exception as e:
            logger.error(f"Failed to check cluster health: {e}")
            raise RedisError(f"Failed to check cluster health: {e}")
    
    def get_key_node_mapping(self, key: str) -> Optional[Dict[str, Any]]:
        """Get the node responsible for a specific key.
        
        Args:
            key: Redis key to check
            
        Returns:
            Dictionary containing node information for the key
        """
        client = self.connection_manager.get_client()
        
        try:
            # Get the slot for this key
            slot = client.cluster_keyslot(key)
            
            # Get cluster slots to find which node handles this slot
            slots_info = self.get_cluster_slots()
            
            for slot_range in slots_info:
                if slot_range["start_slot"] <= slot <= slot_range["end_slot"]:
                    return {
                        "key": key,
                        "slot": slot,
                        "master_node": slot_range["master"],
                        "replica_nodes": slot_range["replicas"]
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get node mapping for key '{key}': {e}")
            raise RedisError(f"Failed to get node mapping for key: {e}")