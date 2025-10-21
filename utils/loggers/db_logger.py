#!/usr/bin/env python3
"""
Database Logger
Specialized logger for database operations and performance
"""

from utils.logger import BaseLogger
from typing import Optional

class DatabaseLogger(BaseLogger):
    """Logger for database operations"""
    
    def __init__(self):
        super().__init__('database')
    
    def connection_established(
        self,
        database: str,
        host: str,
        port: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log database connection establishment"""
        self.info(
            f"Database connection established: {database}@{host}:{port}",
            database=database,
            host=host,
            port=port,
            correlation_id=correlation_id,
            event_type="connection_established"
        )
    
    def connection_failed(
        self,
        database: str,
        host: str,
        port: int,
        error: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log database connection failure"""
        self.error(
            f"Database connection failed: {database}@{host}:{port}, error: {error}",
            database=database,
            host=host,
            port=port,
            error=error,
            correlation_id=correlation_id,
            event_type="connection_failed"
        )
    
    def query_executed(
        self,
        query_type: str,
        table: str,
        duration_ms: float,
        rows_affected: Optional[int] = None,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log database query execution"""
        self.info(
            f"Database query executed: {query_type} on {table}",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            rows_affected=rows_affected,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="query_executed"
        )
    
    def slow_query(
        self,
        query_type: str,
        table: str,
        duration_ms: float,
        threshold_ms: float,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log slow database queries"""
        self.warning(
            f"Slow database query: {query_type} on {table} took {duration_ms}ms (threshold: {threshold_ms}ms)",
            query_type=query_type,
            table=table,
            duration_ms=duration_ms,
            threshold_ms=threshold_ms,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="slow_query"
        )
    
    def query_error(
        self,
        query_type: str,
        table: str,
        error: str,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log database query errors"""
        self.error(
            f"Database query error: {query_type} on {table}, error: {error}",
            query_type=query_type,
            table=table,
            error=error,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="query_error"
        )
    
    def transaction_started(
        self,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log transaction start"""
        self.info(
            "Database transaction started",
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="transaction_started"
        )
    
    def transaction_committed(
        self,
        duration_ms: float,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log transaction commit"""
        self.info(
            f"Database transaction committed in {duration_ms}ms",
            duration_ms=duration_ms,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="transaction_committed"
        )
    
    def transaction_rolled_back(
        self,
        reason: str,
        duration_ms: float,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log transaction rollback"""
        self.warning(
            f"Database transaction rolled back: {reason} (duration: {duration_ms}ms)",
            reason=reason,
            duration_ms=duration_ms,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="transaction_rolled_back"
        )
    
    def connection_pool_status(
        self,
        active_connections: int,
        idle_connections: int,
        max_connections: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log connection pool status"""
        self.info(
            f"Database connection pool status: {active_connections} active, {idle_connections} idle, {max_connections} max",
            active_connections=active_connections,
            idle_connections=idle_connections,
            max_connections=max_connections,
            correlation_id=correlation_id,
            event_type="connection_pool_status"
        )
    
    def migration_executed(
        self,
        migration_name: str,
        duration_ms: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log database migration"""
        self.info(
            f"Database migration executed: {migration_name}",
            migration_name=migration_name,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            event_type="migration_executed"
        )
    
    def backup_started(
        self,
        backup_name: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log backup start"""
        self.info(
            f"Database backup started: {backup_name}",
            backup_name=backup_name,
            correlation_id=correlation_id,
            event_type="backup_started"
        )
    
    def backup_completed(
        self,
        backup_name: str,
        duration_ms: float,
        size_mb: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log backup completion"""
        self.info(
            f"Database backup completed: {backup_name} ({size_mb}MB in {duration_ms}ms)",
            backup_name=backup_name,
            duration_ms=duration_ms,
            size_mb=size_mb,
            correlation_id=correlation_id,
            event_type="backup_completed"
        )

# Create global instance
db_logger = DatabaseLogger()
