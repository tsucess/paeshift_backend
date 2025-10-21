"""
Performance Testing Module for Phase 2.2d
Measures query counts, response times, and cache effectiveness
"""

import time
import json
from typing import Dict, List, Any
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.core.cache import cache
from core.cache_utils import CacheStats


class PerformanceMetrics:
    """Track performance metrics for endpoints"""
    
    def __init__(self):
        self.metrics = {}
        self.baseline = {}
        self.optimized = {}
    
    def record_endpoint(self, endpoint_name: str, query_count: int, response_time: float, cache_hit: bool = False):
        """Record metrics for an endpoint"""
        if endpoint_name not in self.metrics:
            self.metrics[endpoint_name] = []
        
        self.metrics[endpoint_name].append({
            'query_count': query_count,
            'response_time': response_time,
            'cache_hit': cache_hit,
            'timestamp': time.time(),
        })
    
    def get_summary(self, endpoint_name: str) -> Dict[str, Any]:
        """Get summary statistics for an endpoint"""
        if endpoint_name not in self.metrics:
            return {}
        
        data = self.metrics[endpoint_name]
        query_counts = [d['query_count'] for d in data]
        response_times = [d['response_time'] for d in data]
        cache_hits = sum(1 for d in data if d['cache_hit'])
        
        return {
            'endpoint': endpoint_name,
            'total_requests': len(data),
            'avg_query_count': sum(query_counts) / len(query_counts),
            'min_query_count': min(query_counts),
            'max_query_count': max(query_counts),
            'avg_response_time': sum(response_times) / len(response_times),
            'min_response_time': min(response_times),
            'max_response_time': max(response_times),
            'cache_hits': cache_hits,
            'cache_hit_rate': (cache_hits / len(data)) * 100 if data else 0,
        }
    
    def get_all_summaries(self) -> Dict[str, Dict[str, Any]]:
        """Get summaries for all endpoints"""
        return {
            endpoint: self.get_summary(endpoint)
            for endpoint in self.metrics.keys()
        }
    
    def export_json(self, filename: str = 'performance_metrics.json'):
        """Export metrics to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.get_all_summaries(), f, indent=2)
        return filename


class QueryCounter:
    """Context manager to count database queries"""
    
    def __init__(self):
        self.query_count = 0
        self.queries = []
    
    def __enter__(self):
        self.initial_count = len(connection.queries)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.query_count = len(connection.queries) - self.initial_count
        self.queries = connection.queries[self.initial_count:]
    
    def get_queries(self) -> List[str]:
        """Get list of SQL queries executed"""
        return [q['sql'] for q in self.queries]
    
    def print_queries(self):
        """Print all queries executed"""
        print(f"\n{'='*80}")
        print(f"Total Queries: {self.query_count}")
        print(f"{'='*80}")
        for i, query in enumerate(self.queries, 1):
            print(f"\n{i}. {query['sql']}")
            print(f"   Time: {query['time']}s")


class ResponseTimer:
    """Context manager to measure response time"""
    
    def __init__(self):
        self.response_time = 0
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.response_time = (time.time() - self.start_time) * 1000  # Convert to ms


class PerformanceTest:
    """Base class for performance tests"""
    
    def __init__(self, endpoint_name: str):
        self.endpoint_name = endpoint_name
        self.metrics = PerformanceMetrics()
    
    def measure_endpoint(self, func, *args, **kwargs) -> Dict[str, Any]:
        """Measure performance of an endpoint"""
        with QueryCounter() as qc, ResponseTimer() as rt:
            result = func(*args, **kwargs)
        
        cache_stats = CacheStats.get_stats()
        cache_hit = cache_stats.get('hits', 0) > 0
        
        self.metrics.record_endpoint(
            self.endpoint_name,
            qc.query_count,
            rt.response_time,
            cache_hit
        )
        
        return {
            'result': result,
            'query_count': qc.query_count,
            'response_time': rt.response_time,
            'cache_hit': cache_hit,
            'cache_stats': cache_stats,
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        return self.metrics.get_summary(self.endpoint_name)


# Performance Targets
PERFORMANCE_TARGETS = {
    'query_count': {
        'before': 10,  # Average queries before optimization
        'after': 1,    # Average queries after optimization
        'target_reduction': 0.90,  # 90% reduction
    },
    'response_time': {
        'before': 500,  # ms before optimization
        'after': 50,    # ms after optimization
        'target_reduction': 0.90,  # 90% reduction
    },
    'cache_hit_rate': {
        'target': 0.80,  # 80% cache hit rate
    },
}


def validate_performance(metrics: Dict[str, Any]) -> Dict[str, bool]:
    """Validate if performance meets targets"""
    validation = {}
    
    # Check query count reduction
    if 'avg_query_count' in metrics:
        reduction = 1 - (metrics['avg_query_count'] / PERFORMANCE_TARGETS['query_count']['before'])
        validation['query_reduction'] = reduction >= PERFORMANCE_TARGETS['query_count']['target_reduction']
    
    # Check response time reduction
    if 'avg_response_time' in metrics:
        reduction = 1 - (metrics['avg_response_time'] / PERFORMANCE_TARGETS['response_time']['before'])
        validation['response_time_reduction'] = reduction >= PERFORMANCE_TARGETS['response_time']['target_reduction']
    
    # Check cache hit rate
    if 'cache_hit_rate' in metrics:
        validation['cache_hit_rate'] = metrics['cache_hit_rate'] >= (PERFORMANCE_TARGETS['cache_hit_rate']['target'] * 100)
    
    return validation


def print_performance_report(metrics: Dict[str, Any]):
    """Print a formatted performance report"""
    print(f"\n{'='*80}")
    print(f"PERFORMANCE REPORT: {metrics.get('endpoint', 'Unknown')}")
    print(f"{'='*80}")
    
    print(f"\nQuery Count:")
    print(f"  Average: {metrics.get('avg_query_count', 'N/A'):.2f}")
    print(f"  Min: {metrics.get('min_query_count', 'N/A')}")
    print(f"  Max: {metrics.get('max_query_count', 'N/A')}")
    
    print(f"\nResponse Time (ms):")
    print(f"  Average: {metrics.get('avg_response_time', 'N/A'):.2f}")
    print(f"  Min: {metrics.get('min_response_time', 'N/A'):.2f}")
    print(f"  Max: {metrics.get('max_response_time', 'N/A'):.2f}")
    
    print(f"\nCache Performance:")
    print(f"  Cache Hits: {metrics.get('cache_hits', 0)}")
    print(f"  Cache Hit Rate: {metrics.get('cache_hit_rate', 0):.2f}%")
    
    print(f"\nTotal Requests: {metrics.get('total_requests', 0)}")
    print(f"{'='*80}\n")

