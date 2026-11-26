#!/usr/bin/env python3
"""
API Request Logger
Specialized logger for API request/response events
"""

import logging
from utils.logger import BaseLogger
from typing import Optional
import time

class APILogger(BaseLogger):
    """Logger for API request/response events"""
    
    def __init__(self):
        super().__init__('api')
    
    def request_started(
        self,
        method: str,
        endpoint: str,
        ip_address: str,
        user_id: Optional[int] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log API request start"""
        self.info(
            f"API request started: {method} {endpoint}",
            method=method,
            endpoint=endpoint,
            ip_address=ip_address,
            user_id=user_id,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="request_started"
        )
    
    def request_completed(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_ms: float,
        ip_address: str,
        user_id: Optional[int] = None,
        response_size: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log API request completion"""
        level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR
        
        self._log_with_context(
            level,
            f"API request completed: {method} {endpoint} - {status_code}",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration_ms=duration_ms,
            ip_address=ip_address,
            user_id=user_id,
            response_size=response_size,
            correlation_id=correlation_id,
            event_type="request_completed"
        )
    
    def slow_request(
        self,
        method: str,
        endpoint: str,
        duration_ms: float,
        threshold_ms: float,
        ip_address: str,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log slow API requests"""
        self.warning(
            f"Slow API request: {method} {endpoint} took {duration_ms}ms (threshold: {threshold_ms}ms)",
            method=method,
            endpoint=endpoint,
            duration_ms=duration_ms,
            threshold_ms=threshold_ms,
            ip_address=ip_address,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="slow_request"
        )
    
    def validation_error(
        self,
        method: str,
        endpoint: str,
        error_details: str,
        ip_address: str,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log validation errors"""
        self.warning(
            f"Validation error on {method} {endpoint}: {error_details}",
            method=method,
            endpoint=endpoint,
            error_details=error_details,
            ip_address=ip_address,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="validation_error"
        )
    
    def endpoint_hit(
        self,
        endpoint: str,
        method: str,
        ip_address: str,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log endpoint access for analytics"""
        self.info(
            f"Endpoint accessed: {method} {endpoint}",
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="endpoint_hit"
        )
    
    def database_query(
        self,
        query_type: str,
        table: str,
        duration_ms: float,
        endpoint: str,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log database queries"""
        self.info(
            f"Database query: {query_type} on {table}",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            endpoint=endpoint,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="database_query"
        )
    
    def external_api_call(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log external API calls"""
        level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR
        
        self._log_with_context(
            level,
            f"External API call: {method} {service}{endpoint} - {status_code}",
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            event_type="external_api_call"
        )
    
    def cache_hit(
        self,
        cache_key: str,
        endpoint: str,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log cache hits"""
        self.info(
            f"Cache hit for key: {cache_key}",
            cache_key=cache_key,
            endpoint=endpoint,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="cache_hit"
        )
    
    def cache_miss(
        self,
        cache_key: str,
        endpoint: str,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log cache misses"""
        self.info(
            f"Cache miss for key: {cache_key}",
            cache_key=cache_key,
            endpoint=endpoint,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="cache_miss"
        )

# Create global instance
api_logger = APILogger()
