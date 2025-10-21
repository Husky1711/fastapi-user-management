#!/usr/bin/env python3
"""
Clean and Simple Logging System
Production-ready structured logging without complex dependencies
"""

import logging
import logging.handlers
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from contextvars import ContextVar
from config.settings import settings

# Context variables for request tracking (simplified for this version)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar('user_id', default=None)

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra attributes from the log record
        if hasattr(record, 'extra_context') and isinstance(record.extra_context, dict):
            log_entry.update(record.extra_context)

        return json.dumps(log_entry)

class LoggerConfig:
    """Simple logging configuration"""
    
    LOG_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    DEFAULT_LOG_LEVEL = 'INFO'
    DEFAULT_LOG_DIR = 'logs'
    DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    DEFAULT_BACKUP_COUNT = 5
    
    @classmethod
    def setup_logging(
        cls,
        log_level: str = None,
        log_dir: str = None,
        max_file_size: int = None,
        backup_count: int = None,
        enable_console: bool = True
    ) -> None:
        """
        Setup application logging configuration
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory to store log files
            max_file_size: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            enable_console: Whether to enable console logging
        """
        # Use centralized settings instead of environment variables
        log_config = settings.get_log_config()
        log_level = log_level or log_config["level"]
        log_dir = log_dir or log_config["log_dir"]
        max_file_size = max_file_size or log_config["max_file_size"]
        backup_count = backup_count or log_config["backup_count"]
        enable_console = enable_console if enable_console is not None else log_config["enable_console"]
        
        # Create log directory if it doesn't exist
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(cls.LOG_LEVELS.get(log_level.upper(), logging.INFO))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Create formatters
        json_formatter = JSONFormatter()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, 'app.log'),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        root_logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, 'error.log'),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setFormatter(json_formatter)
        error_handler.setLevel(logging.ERROR)  # Only errors and above
        root_logger.addHandler(error_handler)
        
        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(cls.LOG_LEVELS.get(log_level.upper(), logging.INFO))
            root_logger.addHandler(console_handler)
        
        # Security log handler
        security_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, 'security.log'),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        security_handler.setFormatter(json_formatter)
        security_handler.setLevel(logging.INFO)
        root_logger.addHandler(security_handler)
        
        # Performance log handler
        performance_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, 'performance.log'),
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        performance_handler.setFormatter(json_formatter)
        performance_handler.setLevel(logging.INFO)
        root_logger.addHandler(performance_handler)
    
    @classmethod
    def get_handlers(cls):
        """Get all configured handlers"""
        return logging.getLogger().handlers

class BaseLogger:
    """Base logger class with common functionality"""
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO)
        
        # Ensure handlers are only added once
        if not self._logger.handlers:
            for handler in LoggerConfig.get_handlers():
                self._logger.addHandler(handler)
            self._logger.propagate = False  # Prevent logs from going to root logger

    def _log_with_context(self, level: int, message: str, **kwargs: Any):
        """Logs a message with additional context"""
        # Attach extra context to the LogRecord
        extra_context = kwargs
        record = self._logger.makeRecord(
            self._logger.name, level, self._logger.findCaller(stack_info=False),
            message, [], None, None, extra=extra_context
        )
        record.extra_context = extra_context  # Store for JsonFormatter
        self._logger.handle(record)

    def debug(self, message: str, **kwargs: Any):
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any):
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any):
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any):
        self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any):
        self._log_with_context(logging.CRITICAL, message, **kwargs)

# Initialize logging configuration
LoggerConfig.setup_logging()

# Create main application logger
app_logger = BaseLogger('app')

# Example usage and testing
if __name__ == "__main__":
    # Test the logging system
    app_logger.info("Testing clean logging system...", event_type="logging_test_start")
    
    # Test basic logging
    app_logger.info("Application started", event_type="app_startup")
    app_logger.warning("This is a warning message", category="test")
    app_logger.error("This is an error message", error_code=500)
    
    # Test logging with context
    app_logger.info(
        "User login successful",
        user_id=123,
        ip_address="192.168.1.1",
        correlation_id="req-12345",
        duration_ms=150.5,
        endpoint="/api/login",
        event_type="user_login"
    )
    
    print("Clean logging test completed. Check the 'logs' directory for output.")