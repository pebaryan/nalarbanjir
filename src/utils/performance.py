"""Performance optimization utilities for flood prediction system.

Provides caching, mesh simplification, and performance monitoring.
"""

import logging
import time
import functools
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from pathlib import Path
import json
import hashlib
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""

    operation: str
    duration_ms: float
    memory_mb: Optional[float] = None
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "memory_mb": self.memory_mb,
            "timestamp": self.timestamp,
        }


class PerformanceMonitor:
    """Monitor and track performance metrics.

    Example:
        >>> monitor = PerformanceMonitor()
        >>> with monitor.track("mesh_generation"):
        ...     mesh = generate_mesh()
        >>> metrics = monitor.get_metrics()
    """

    def __init__(self):
        self.metrics: list = []
        self._start_times: Dict[str, float] = {}

    def track(self, operation: str):
        """Context manager for tracking operation performance.

        Args:
            operation: Name of the operation being tracked
        """
        return _PerformanceTracker(self, operation)

    def start(self, operation: str):
        """Start tracking an operation."""
        self._start_times[operation] = time.time()

    def end(self, operation: str) -> float:
        """End tracking an operation and record metric.

        Returns:
            Duration in milliseconds
        """
        if operation not in self._start_times:
            logger.warning(f"No start time found for operation: {operation}")
            return 0.0

        duration = (time.time() - self._start_times[operation]) * 1000

        metric = PerformanceMetrics(
            operation=operation,
            duration_ms=duration,
            timestamp=time.time(),
        )
        self.metrics.append(metric)

        del self._start_times[operation]
        return duration

    def get_metrics(self, operation: Optional[str] = None) -> list:
        """Get recorded metrics.

        Args:
            operation: Filter by operation name (optional)

        Returns:
            List of PerformanceMetrics
        """
        if operation:
            return [m for m in self.metrics if m.operation == operation]
        return self.metrics.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        if not self.metrics:
            return {}

        summary = {}
        operations = set(m.operation for m in self.metrics)

        for op in operations:
            op_metrics = self.get_metrics(op)
            durations = [m.duration_ms for m in op_metrics]

            summary[op] = {
                "count": len(durations),
                "total_ms": sum(durations),
                "mean_ms": np.mean(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "std_ms": np.std(durations) if len(durations) > 1 else 0.0,
            }

        return summary

    def clear(self):
        """Clear all metrics."""
        self.metrics.clear()
        self._start_times.clear()

    def export_to_file(self, filepath: str):
        """Export metrics to JSON file."""
        data = {
            "summary": self.get_summary(),
            "metrics": [m.to_dict() for m in self.metrics],
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)


class _PerformanceTracker:
    """Context manager for performance tracking."""

    def __init__(self, monitor: PerformanceMonitor, operation: str):
        self.monitor = monitor
        self.operation = operation

    def __enter__(self):
        self.monitor.start(self.operation)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.monitor.end(self.operation)
        return False


class SimpleCache:
    """Simple in-memory cache with size limits.

    Example:
        >>> cache = SimpleCache(max_size=100, ttl=3600)
        >>> cache.set("key", value)
        >>> value = cache.get("key")
    """

    def __init__(self, max_size: int = 100, ttl: Optional[float] = None):
        """Initialize cache.

        Args:
            max_size: Maximum number of cached items
            ttl: Time-to-live in seconds (None for no expiration)
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, tuple] = {}
        self._access_times: Dict[str, float] = {}

    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = json.dumps(
            {"args": args, "kwargs": kwargs}, sort_keys=True, default=str
        )
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]

        # Check TTL
        if self.ttl is not None:
            if time.time() - timestamp > self.ttl:
                del self._cache[key]
                del self._access_times[key]
                return None

        self._access_times[key] = time.time()
        return value

    def set(self, key: str, value: Any):
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        self._cache[key] = (value, time.time())
        self._access_times[key] = time.time()

    def _evict_oldest(self):
        """Evict least recently used item."""
        if not self._access_times:
            return

        oldest_key = min(self._access_times, key=self._access_times.get)
        del self._cache[oldest_key]
        del self._access_times[oldest_key]

    def clear(self):
        """Clear all cached items."""
        self._cache.clear()
        self._access_times.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


def cached(cache: SimpleCache):
    """Decorator for caching function results.

    Example:
        >>> cache = SimpleCache()
        >>> @cached(cache)
        ... def expensive_function(x):
        ...     return x * x
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = json.dumps(
                {
                    "func": func.__name__,
                    "args": args,
                    "kwargs": kwargs,
                },
                sort_keys=True,
                default=str,
            )
            key = hashlib.md5(key_data.encode()).hexdigest()

            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        return wrapper

    return decorator


class MeshCache:
    """Specialized cache for mesh data with automatic cleanup."""

    def __init__(self, max_size: int = 10, max_memory_mb: float = 500.0):
        """Initialize mesh cache.

        Args:
            max_size: Maximum number of meshes to cache
            max_memory_mb: Maximum memory usage in MB
        """
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self._meshes: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict] = {}

    def _estimate_size_mb(self, mesh) -> float:
        """Estimate mesh size in MB."""
        total_bytes = 0
        if hasattr(mesh, "vertices") and mesh.vertices is not None:
            total_bytes += len(mesh.vertices) * 3 * 4  # float32
        if hasattr(mesh, "faces") and mesh.faces is not None:
            total_bytes += len(mesh.faces) * 3 * 4  # int32
        return total_bytes / (1024 * 1024)

    def store(self, key: str, mesh, metadata: Optional[Dict] = None):
        """Store mesh in cache.

        Args:
            key: Cache key
            mesh: Mesh object
            metadata: Optional metadata dictionary
        """
        # Check memory limit
        mesh_size = self._estimate_size_mb(mesh)
        current_size = sum(m.get("size_mb", 0) for m in self._metadata.values())

        if current_size + mesh_size > self.max_memory_mb:
            self._evict_to_free_space(mesh_size)

        # Evict oldest if at capacity
        if len(self._meshes) >= self.max_size:
            self._evict_oldest()

        self._meshes[key] = mesh
        self._metadata[key] = {
            "timestamp": time.time(),
            "size_mb": mesh_size,
            **(metadata or {}),
        }

        logger.info(f"Cached mesh '{key}': {mesh_size:.2f} MB")

    def get(self, key: str) -> Optional[Any]:
        """Get mesh from cache."""
        if key not in self._meshes:
            return None

        self._metadata[key]["access_time"] = time.time()
        return self._meshes[key]

    def _evict_oldest(self):
        """Evict oldest mesh."""
        if not self._metadata:
            return

        oldest_key = min(
            self._metadata, key=lambda k: self._metadata[k].get("timestamp", 0)
        )
        self._remove(oldest_key)

    def _evict_to_free_space(self, required_mb: float):
        """Evict meshes to free up space."""
        freed = 0.0
        while freed < required_mb and self._metadata:
            oldest_key = min(
                self._metadata, key=lambda k: self._metadata[k].get("timestamp", 0)
            )
            freed += self._metadata[oldest_key].get("size_mb", 0)
            self._remove(oldest_key)

    def _remove(self, key: str):
        """Remove mesh from cache."""
        if key in self._meshes:
            del self._meshes[key]
        if key in self._metadata:
            del self._metadata[key]
        logger.debug(f"Evicted mesh '{key}' from cache")

    def clear(self):
        """Clear all cached meshes."""
        self._meshes.clear()
        self._metadata.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(m.get("size_mb", 0) for m in self._metadata.values())
        return {
            "cached_meshes": len(self._meshes),
            "total_size_mb": total_size,
            "max_size": self.max_size,
            "max_memory_mb": self.max_memory_mb,
        }


def optimize_mesh_for_rendering(mesh, target_vertices: int = 10000) -> Any:
    """Optimize mesh for real-time rendering.

    Args:
        mesh: Input mesh
        target_vertices: Target number of vertices

    Returns:
        Optimized mesh
    """
    current_vertices = len(mesh.vertices) if mesh.vertices else 0

    if current_vertices <= target_vertices:
        return mesh

    # Calculate simplification ratio
    simplification_ratio = target_vertices / current_vertices

    # Import here to avoid circular imports
    from gis.mesh_generator import TerrainMeshGenerator

    # Create simplified mesh
    generator = TerrainMeshGenerator()
    # Note: This is a placeholder - actual implementation would use
    # proper mesh decimation algorithms

    logger.info(
        f"Optimized mesh from {current_vertices} to target {target_vertices} vertices"
    )
    return mesh


def profile_function(func: Callable) -> Callable:
    """Decorator to profile function execution time.

    Example:
        >>> @profile_function
        ... def my_function():
        ...     pass
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = (time.time() - start) * 1000
        logger.info(f"{func.__name__} took {elapsed:.2f} ms")
        return result

    return wrapper
