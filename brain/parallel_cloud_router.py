import os
import random
from typing import Dict, Any
from loguru import logger
import httpx

class ParallelCloudRouter:
    """
    Parallel multi-cloud distribution.
    ALL providers are active simultaneously.
    Workload is distributed based on capacity, weight, and health.
    """
    
    PROVIDERS = {
        "gcp_cloud_run": {
            "url": os.getenv("GCP_CLOUD_RUN_URL", ""),
            "weight": 40.0,  # 40% traffic (highest - free tier)
            "capacity": 2000000,  # 2M requests/month
            "current_requests": 0,
            "status": "active",
            "region": "us-central1",
            "latency_ms": 50.0,
        },
        "railway": {
            "url": os.getenv("RAILWAY_URL", ""),
            "weight": 35.0,  # 35% traffic
            "capacity": 500000,  # $5 = ~500K requests
            "current_requests": 0,
            "status": "active",
            "region": "us-east",
            "latency_ms": 80.0,
        },
        "render": {
            "url": os.getenv("RENDER_URL", ""),
            "weight": 25.0,  # 25% traffic
            "capacity": 180000,  # ~180K requests (750 hours free)
            "current_requests": 0,
            "status": "active",
            "region": "oregon",
            "latency_ms": 120.0,
        }
    }
    
    def __init__(self):
        self._health_check_all()
    
    def _health_check_all(self):
        """Check health of all providers."""
        for name, config in self.PROVIDERS.items():
            if not config["url"]:
                # If no URL is provided in env, mark as inactive but don't fail completely
                config["status"] = "inactive"
                continue
                
            try:
                response = httpx.get(
                    f"{config['url'].rstrip('/')}/health", 
                    timeout=5.0
                )
                if response.status_code == 200:
                    config["status"] = "active"
                    config["latency_ms"] = response.elapsed.total_seconds() * 1000
                else:
                    config["status"] = "degraded"
            except Exception as e:
                logger.warning(f"{name} health check failed: {e}")
                config["status"] = "down"
    
    def get_provider_for_request(self, task_type: str = "general") -> str:
        """
        Weighted selection with health awareness.
        All active providers get traffic based on their capacity and configured weights.
        """
        active_providers = {
            name: config for name, config in self.PROVIDERS.items()
            if config["status"] in ["active", "degraded"] 
            and config["url"]
        }
        
        if not active_providers:
            logger.warning("ALL PROVIDERS DOWN or unconfigured! Falling back to local/default.")
            # Return any provider that has a URL, otherwise default to gcp_cloud_run
            configured = [name for name, config in self.PROVIDERS.items() if config["url"]]
            return configured[0] if configured else "gcp_cloud_run"
        
        # Calculate dynamic weights based on remaining capacity
        total_weight = 0.0
        weights = {}
        
        for name, config in active_providers.items():
            # Remaining capacity ratio
            used_ratio = config["current_requests"] / max(config["capacity"], 1)
            remaining_weight = config["weight"] * (1.0 - used_ratio)
            
            # Boost for low latency
            latency_boost = max(0.0, (200.0 - config["latency_ms"]) / 200.0)
            final_weight = remaining_weight * (1.0 + latency_boost)
            
            weights[name] = max(final_weight, 1.0)  # Minimum weight of 1.0
            total_weight += weights[name]
        
        # Weighted random selection
        pick = random.uniform(0.0, total_weight)
        current = 0.0
        
        for name, weight in weights.items():
            current += weight
            if pick <= current:
                self.PROVIDERS[name]["current_requests"] += 1
                return name
        
        return list(active_providers.keys())[0]
    
    def route_parallel(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route request to one provider.
        """
        provider = self.get_provider_for_request(payload.get("task_type", "general"))
        config = self.PROVIDERS[provider]
        url = f"{config['url'].rstrip('/')}{endpoint}"
        
        try:
            response = httpx.post(url, json=payload, timeout=30.0)
            result = response.json()
            result["_provider"] = provider
            result["_region"] = config["region"]
            return result
        except Exception as e:
            logger.error(f"{provider} failed: {e}")
            # Mark down and fallback
            self.PROVIDERS[provider]["status"] = "down"
            self.PROVIDERS[provider]["current_requests"] = max(0, self.PROVIDERS[provider]["current_requests"] - 1)
            return self.route_parallel(endpoint, payload)
    
    def get_distribution_stats(self) -> Dict[str, Any]:
        """Get current traffic distribution across all providers."""
        return {
            name: {
                "status": config["status"],
                "current_requests": config["current_requests"],
                "capacity_remaining": max(0, config["capacity"] - config["current_requests"]),
                "utilization_pct": (config["current_requests"] / max(config["capacity"], 1)) * 100.0,
                "latency_ms": config["latency_ms"],
                "region": config["region"],
            }
            for name, config in self.PROVIDERS.items()
        }
    
    def rebalance(self):
        """
        Rebalance weights based on actual usage.
        """
        for name, config in self.PROVIDERS.items():
            if config["status"] != "active":
                continue
            utilization = (config["current_requests"] / max(config["capacity"], 1)) * 100.0
            if utilization > 80.0:
                config["weight"] *= 0.8
                logger.info(f"Reduced weight for {name} due to high utilization")
            elif utilization < 20.0:
                config["weight"] = min(config["weight"] * 1.2, 50.0)
                logger.info(f"Increased weight for {name} due to low utilization")
        
        # Normalize weights
        active_provs = [c for c in self.PROVIDERS.values() if c["status"] == "active"]
        total = sum(p["weight"] for p in active_provs)
        if total > 0:
            for name, config in self.PROVIDERS.items():
                if config["status"] == "active":
                    config["weight"] = (config["weight"] / total) * 100.0
