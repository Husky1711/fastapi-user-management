#!/usr/bin/env python3
"""
Production Logging Features
Correlation IDs, Performance Metrics, and Request Tracking
"""

import uuid
import time
import functools
import asyncio
from typing import Optional, Dict, Any, Callable
from contextvars import ContextVar
from utils.loggers import api_logger, auth_logger, db_logger, security_logger

# Context variables for request tracking
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar('user_id', default=None)
request_start_time_var: ContextVar[Optional[float]] = ContextVar('request_start_time', default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)

class CorrelationIDGenerator:
    """Generate and manage correlation IDs"""
    
    @staticmethod
    def generate() -> str:
        """Generate a new correlation ID"""
        return str(uuid.uuid4())
    
    @staticmethod
    def get_current() -> Optional[str]:
        """Get current correlation ID from context"""
        return correlation_id_var.get()
    
    @staticmethod
    def set(correlation_id: str) -> None:
        """Set correlation ID in context"""
        correlation_id_var.set(correlation_id)

class PerformanceMetrics:
    """Collect and track performance metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
    
    def start_timer(self, operation: str) -> float:
        """Start timing an operation"""
        start_time = time.time()
        self.metrics[f"{operation}_start"] = start_time
        return start_time
    
    def end_timer(self, operation: str) -> float:
        """End timing an operation and return duration"""
        end_time = time.time()
        start_time = self.metrics.get(f"{operation}_start", end_time)
        duration_ms = (end_time - start_time) * 1000
        self.metrics[f"{operation}_duration_ms"] = duration_ms
        return duration_ms
    
    def record_metric(self, name: str, value: Any) -> None:
        """Record a custom metric"""
        self.metrics[name] = value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics"""
        return self.metrics.copy()

class RequestContext:
    """Manage request context and correlation"""
    
    def __init__(self):
        self.correlation_id: Optional[str] = None
        self.user_id: Optional[int] = None
        self.start_time: Optional[float] = None
        self.metrics = PerformanceMetrics()
        self.request_data: Dict[str, Any] = {}
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID"""
        self.correlation_id = correlation_id
        CorrelationIDGenerator.set(correlation_id)
    
    def set_user_id(self, user_id: int) -> None:
        """Set user ID"""
        self.user_id = user_id
        user_id_var.set(user_id)
    
    def set_start_time(self, start_time: float) -> None:
        """Set request start time"""
        self.start_time = start_time
        request_start_time_var.set(start_time)
    
    def get_duration_ms(self) -> Optional[float]:
        """Get request duration in milliseconds"""
        if self.start_time:
            return (time.time() - self.start_time) * 1000
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging"""
        return {
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "duration_ms": self.get_duration_ms(),
            "metrics": self.metrics.get_metrics(),
            "request_data": self.request_data
        }

def log_performance(operation_name: str):
    """Decorator to log performance of functions"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Log performance
                api_logger.info(
                    f"Operation completed: {operation_name}",
                    operation=operation_name,
                    duration_ms=duration_ms,
                    correlation_id=CorrelationIDGenerator.get_current(),
                    event_type="operation_completed"
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # Log error
                api_logger.error(
                    f"Operation failed: {operation_name}",
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e),
                    correlation_id=CorrelationIDGenerator.get_current(),
                    event_type="operation_failed"
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Log performance
                api_logger.info(
                    f"Operation completed: {operation_name}",
                    operation=operation_name,
                    duration_ms=duration_ms,
                    correlation_id=CorrelationIDGenerator.get_current(),
                    event_type="operation_completed"
                )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # Log error
                api_logger.error(
                    f"Operation failed: {operation_name}",
                    operation=operation_name,
                    duration_ms=duration_ms,
                    error=str(e),
                    correlation_id=CorrelationIDGenerator.get_current(),
                    event_type="operation_failed"
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def get_request_context() -> Optional[RequestContext]:
    """Get current request context from ContextVars."""
    correlation_id = CorrelationIDGenerator.get_current()
    if not correlation_id:
        return None
    context = RequestContext()
    context.correlation_id = correlation_id
    context.user_id = user_id_var.get()
    context.start_time = request_start_time_var.get()
    return context
