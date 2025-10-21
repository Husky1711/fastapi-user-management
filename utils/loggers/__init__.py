#!/usr/bin/env python3
"""
Main Logger Module
Centralized access to all application loggers
"""

# Import all specialized loggers
from utils.loggers.auth_logger import auth_logger
from utils.loggers.api_logger import api_logger
from utils.loggers.db_logger import db_logger
from utils.loggers.security_logger import security_logger

# Import base logger for general use
from utils.logger import BaseLogger

# Create general application logger
app_logger = BaseLogger('app')

# Export all loggers for easy importing
__all__ = [
    'app_logger',
    'auth_logger', 
    'api_logger',
    'db_logger',
    'security_logger'
]

# Example usage:
# from utils.loggers import auth_logger, api_logger, db_logger, security_logger
# 
# auth_logger.login_success(user_id=123, username="john", ip_address="192.168.1.1", duration_ms=150)
# api_logger.request_completed("GET", "/api/users", 200, 250.5, "192.168.1.1")
# db_logger.query_executed("SELECT", "users", 45.2, rows_affected=10)
# security_logger.rate_limit_exceeded("192.168.1.1", "/api/login", "minute", 10, 11)
