#!/usr/bin/env python3
"""
Request Context Manager
Enhanced request tracking and correlation management
"""

import time
import uuid
from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager
from fastapi import Request
from utils.loggers import api_logger, auth_logger, db_logger, security_logger

class RequestTracker:
    """Track request context and performance"""
    
    def __init__(self, request: Request):
        self.request = request
        self.correlation_id = str(uuid.uuid4())
        self.start_time = time.time()
        self.user_id: Optional[int] = None
        self.operation_timers: Dict[str, float] = {}
        self.custom_metrics: Dict[str, Any] = {}
        self.tags: Dict[str, str] = {}
        
        # Extract request information
        self.method = request.method
        self.endpoint = str(request.url.path)
        self.ip_address = request.client.host if request.client else "unknown"
        self.user_agent = request.headers.get("user-agent", "unknown")
        
        # Set correlation ID in request state
        request.state.correlation_id = self.correlation_id
        request.state.tracker = self
    
    def set_user_id(self, user_id: int) -> None:
        """Set user ID for the request"""
        self.user_id = user_id
    
    def start_operation(self, operation_name: str) -> None:
        """Start timing an operation"""
        self.operation_timers[operation_name] = time.time()
    
    def end_operation(self, operation_name: str) -> float:
        """End timing an operation and return duration"""
        if operation_name not in self.operation_timers:
            return 0.0
        
        duration_ms = (time.time() - self.operation_timers[operation_name]) * 1000
        del self.operation_timers[operation_name]
        
        # Log operation completion
        api_logger.info(
            f"Operation completed: {operation_name}",
            operation=operation_name,
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
            user_id=self.user_id,
            endpoint=self.endpoint,
            event_type="operation_completed"
        )
        
        return duration_ms
    
    def add_metric(self, name: str, value: Any) -> None:
        """Add a custom metric"""
        self.custom_metrics[name] = value
    
    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the request"""
        self.tags[key] = value
    
    def get_duration_ms(self) -> float:
        """Get total request duration in milliseconds"""
        return (time.time() - self.start_time) * 1000
    
    def log_request_start(self) -> None:
        """Log request start"""
        api_logger.request_started(
            method=self.method,
            endpoint=self.endpoint,
            ip_address=self.ip_address,
            user_id=self.user_id,
            user_agent=self.user_agent,
            correlation_id=self.correlation_id
        )
    
    def log_request_complete(self, status_code: int, response_size: Optional[int] = None) -> None:
        """Log request completion"""
        duration_ms = self.get_duration_ms()
        
        api_logger.request_completed(
            method=self.method,
            endpoint=self.endpoint,
            status_code=status_code,
            duration_ms=duration_ms,
            ip_address=self.ip_address,
            user_id=self.user_id,
            response_size=response_size,
            correlation_id=self.correlation_id
        )
        
        # Log slow requests
        if duration_ms > 1000:  # > 1 second
            api_logger.slow_request(
                method=self.method,
                endpoint=self.endpoint,
                duration_ms=duration_ms,
                threshold_ms=1000,
                ip_address=self.ip_address,
                user_id=self.user_id,
                correlation_id=self.correlation_id
            )
    
    def log_request_error(self, error: Exception) -> None:
        """Log request error"""
        duration_ms = self.get_duration_ms()
        
        api_logger.error(
            f"Request failed: {self.method} {self.endpoint}",
            method=self.method,
            endpoint=self.endpoint,
            error=str(error),
            duration_ms=duration_ms,
            ip_address=self.ip_address,
            user_id=self.user_id,
            correlation_id=self.correlation_id,
            event_type="request_error"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tracker to dictionary"""
        return {
            "correlation_id": self.correlation_id,
            "method": self.method,
            "endpoint": self.endpoint,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "user_id": self.user_id,
            "duration_ms": self.get_duration_ms(),
            "start_time": self.start_time,
            "custom_metrics": self.custom_metrics,
            "tags": self.tags
        }

@contextmanager
def track_request(request: Request) -> Generator[RequestTracker, None, None]:
    """Context manager for request tracking"""
    tracker = RequestTracker(request)
    
    try:
        tracker.log_request_start()
        yield tracker
    except Exception as e:
        tracker.log_request_error(e)
        raise
    finally:
        # Log any remaining operations
        for operation_name in list(tracker.operation_timers.keys()):
            tracker.end_operation(operation_name)

@contextmanager
def track_operation(tracker: RequestTracker, operation_name: str) -> Generator[None, None, None]:
    """Context manager for operation tracking"""
    tracker.start_operation(operation_name)
    
    try:
        yield
    finally:
        tracker.end_operation(operation_name)

def get_request_tracker(request: Request) -> Optional[RequestTracker]:
    """Get request tracker from request state"""
    return getattr(request.state, 'tracker', None)

def log_auth_event(
    event_type: str,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    success: bool = True,
    error: Optional[str] = None,
    tracker: Optional[RequestTracker] = None
) -> None:
    """Log authentication event with request context"""
    correlation_id = tracker.correlation_id if tracker else None
    ip_address = tracker.ip_address if tracker else None
    user_agent = tracker.user_agent if tracker else None
    
    if event_type == "login_attempt":
        auth_logger.login_attempt(username or "unknown", ip_address or "unknown", user_agent, correlation_id)
    elif event_type == "login_success":
        auth_logger.login_success(user_id or 0, username or "unknown", ip_address or "unknown", 0, user_agent, correlation_id)
    elif event_type == "login_failure":
        auth_logger.login_failure(username or "unknown", ip_address or "unknown", error or "unknown", user_agent, correlation_id)
    elif event_type == "signup_attempt":
        auth_logger.signup_attempt(username or "unknown", "unknown@example.com", ip_address or "unknown", user_agent, correlation_id)
    elif event_type == "signup_success":
        auth_logger.signup_success(user_id or 0, username or "unknown", "unknown@example.com", ip_address or "unknown", 0, user_agent, correlation_id)
    elif event_type == "signup_failure":
        auth_logger.signup_failure(username or "unknown", "unknown@example.com", ip_address or "unknown", error or "unknown", user_agent, correlation_id)

def log_db_event(
    event_type: str,
    query_type: str,
    table: str,
    duration_ms: float,
    error: Optional[str] = None,
    tracker: Optional[RequestTracker] = None
) -> None:
    """Log database event with request context"""
    correlation_id = tracker.correlation_id if tracker else None
    user_id = tracker.user_id if tracker else None
    
    if event_type == "query_executed":
        db_logger.query_executed(query_type, table, duration_ms, user_id=user_id, correlation_id=correlation_id)
    elif event_type == "query_error":
        db_logger.query_error(query_type, table, error or "unknown", user_id=user_id, correlation_id=correlation_id)
    elif event_type == "slow_query":
        db_logger.slow_query(query_type, table, duration_ms, 1000.0, user_id=user_id, correlation_id=correlation_id)

def log_security_event(
    event_type: str,
    ip_address: Optional[str] = None,
    endpoint: Optional[str] = None,
    details: Optional[str] = None,
    tracker: Optional[RequestTracker] = None
) -> None:
    """Log security event with request context"""
    correlation_id = tracker.correlation_id if tracker else None
    ip_addr = ip_address or (tracker.ip_address if tracker else None)
    ep = endpoint or (tracker.endpoint if tracker else None)
    
    if event_type == "rate_limit_exceeded":
        security_logger.rate_limit_exceeded(ip_addr or "unknown", ep or "unknown", "minute", 10, 11, correlation_id=correlation_id)
    elif event_type == "suspicious_activity":
        security_logger.suspicious_activity("unknown", ip_addr or "unknown", details=details, correlation_id=correlation_id)
    elif event_type == "unauthorized_access":
        security_logger.unauthorized_access_attempt(ep or "unknown", "GET", ip_addr or "unknown", correlation_id=correlation_id)
