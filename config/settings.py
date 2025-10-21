#!/usr/bin/env python3
"""
Centralized Configuration Management
Using Pydantic Settings for type-safe configuration
"""

import os
from typing import Dict, Any, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path

class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    url: str = Field("mysql+pymysql://root:Sandhya%40332@localhost:3306/fastapi_users", description="Database connection URL")
    echo: bool = Field(False, description="Enable SQLAlchemy echo for debugging")
    pool_size: int = Field(10, description="Database connection pool size")
    max_overflow: int = Field(20, description="Maximum overflow connections")
    
    class Config:
        env_prefix = "DB_"

class RedisSettings(BaseSettings):
    """Redis configuration settings"""
    host: str = Field("localhost", description="Redis host")
    port: int = Field(6379, description="Redis port")
    db: int = Field(0, description="Redis database number")
    password: Optional[str] = Field(None, description="Redis password")
    socket_connect_timeout: int = Field(5, description="Socket connect timeout")
    socket_timeout: int = Field(5, description="Socket timeout")
    retry_on_timeout: bool = Field(True, description="Retry on timeout")
    
    class Config:
        env_prefix = "REDIS_"

class JWTSettings(BaseSettings):
    """JWT configuration settings"""
    secret_key: str = Field("your-super-secret-key-change-this-in-production-must-be-at-least-32-chars", description="JWT secret key")
    algorithm: str = Field("HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(5, description="Access token expiration in minutes")
    refresh_token_expire_days: int = Field(7, description="Refresh token expiration in days")
    
    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v):
        if len(v) < 32:
            raise ValueError('Secret key must be at least 32 characters long')
        return v
    
    class Config:
        env_prefix = "JWT_"

class RateLimitSettings(BaseSettings):
    """Rate limiting configuration settings"""
    
    # Endpoint-specific rate limits
    endpoint_limits: Dict[str, Dict[str, int]] = Field(
        default={
            "users_list": {"minute": 5, "hour": 50},
            "user_detail": {"minute": 20, "hour": 200},
            "sessions": {"minute": 10, "hour": 100},
            "session_revoke": {"minute": 5, "hour": 50},
            "login": {"minute": 10, "hour": 100},
            "refresh": {"minute": 20, "hour": 200},
            "signup": {"minute": 5, "hour": 50},
        },
        description="Rate limits for specific endpoints"
    )
    
    # Global IP limits (DDoS protection)
    global_ip_limits: Dict[str, int] = Field(
        default={
            "minute": 1000,
            "hour": 10000,
            "day": 100000
        },
        description="Global IP rate limits"
    )
    
    # Rate limiting behavior
    fail_open: bool = Field(True, description="Allow requests if Redis is down")
    enable_user_limits: bool = Field(True, description="Enable user-specific rate limits")
    enable_ip_limits: bool = Field(True, description="Enable IP-based rate limits")
    
    class Config:
        env_prefix = "RATE_LIMIT_"

class LoggingSettings(BaseSettings):
    """Logging configuration settings"""
    level: str = Field("INFO", description="Logging level")
    log_dir: str = Field("logs", description="Log directory")
    max_file_size: int = Field(10 * 1024 * 1024, description="Max log file size in bytes")  # 10MB
    backup_count: int = Field(5, description="Number of backup files to keep")
    enable_console: bool = Field(True, description="Enable console logging")
    enable_file: bool = Field(True, description="Enable file logging")
    enable_json: bool = Field(True, description="Enable JSON formatted logs")
    
    # Log rotation settings
    rotation_enabled: bool = Field(True, description="Enable log rotation")
    rotation_schedule: str = Field("daily", description="Log rotation schedule")
    retention_days: int = Field(30, description="Log retention in days")
    
    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()
    
    class Config:
        env_prefix = "LOG_"

class SecuritySettings(BaseSettings):
    """Security configuration settings"""
    enable_cors: bool = Field(True, description="Enable CORS")
    cors_origins: list = Field(["*"], description="CORS allowed origins")
    enable_https_redirect: bool = Field(False, description="Enable HTTPS redirect")
    session_timeout_minutes: int = Field(30, description="Session timeout in minutes")
    max_login_attempts: int = Field(5, description="Maximum login attempts")
    lockout_duration_minutes: int = Field(15, description="Account lockout duration")
    
    class Config:
        env_prefix = "SECURITY_"

class AppSettings(BaseSettings):
    """Main application settings"""
    name: str = Field("FastAPI User Management", description="Application name")
    version: str = Field("1.0.0", description="Application version")
    description: str = Field("Role-based multi-tenant user management system", description="Application description")
    debug: bool = Field(False, description="Debug mode")
    host: str = Field("localhost", description="Server host")
    port: int = Field(9000, description="Server port")
    reload: bool = Field(False, description="Auto-reload on code changes")
    
    # Environment
    environment: str = Field("development", description="Environment (development/staging/production)")
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production']
        if v.lower() not in valid_envs:
            raise ValueError(f'Environment must be one of: {valid_envs}')
        return v.lower()
    
    class Config:
        env_prefix = "APP_"

class Settings(BaseSettings):
    """Main settings class that combines all configuration sections"""
    
    # Configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    app: AppSettings = Field(default_factory=AppSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        extra = "ignore"  # Ignore extra fields from environment
        
        # Allow nested env vars
        env_nested_delimiter = "__"
    
    def get_database_url(self) -> str:
        """Get database URL with validation"""
        return self.database.url
    
    def get_redis_url(self) -> str:
        """Get Redis URL"""
        password_part = f":{self.redis.password}@" if self.redis.password else ""
        return f"redis://{password_part}{self.redis.host}:{self.redis.port}/{self.redis.db}"
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment.lower() == "development"
    
    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            "level": self.logging.level,
            "log_dir": self.logging.log_dir,
            "max_file_size": self.logging.max_file_size,
            "backup_count": self.logging.backup_count,
            "enable_console": self.logging.enable_console,
            "enable_file": self.logging.enable_file,
            "enable_json": self.logging.enable_json,
            "rotation_enabled": self.logging.rotation_enabled,
            "rotation_schedule": self.logging.rotation_schedule,
            "retention_days": self.logging.retention_days,
        }

# Global settings instance
settings = Settings()

# Export commonly used settings for backward compatibility
DATABASE_URL = settings.get_database_url()
REDIS_HOST = settings.redis.host
REDIS_PORT = settings.redis.port
REDIS_DB = settings.redis.db
REDIS_PASSWORD = settings.redis.password
JWT_SECRET_KEY = settings.jwt.secret_key
JWT_ALGORITHM = settings.jwt.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.jwt.access_token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = settings.jwt.refresh_token_expire_days
ENDPOINT_LIMITS = settings.rate_limit.endpoint_limits
GLOBAL_IP_LIMITS = settings.rate_limit.global_ip_limits

if __name__ == "__main__":
    # Test configuration loading
    print("Configuration loaded successfully!")
    print(f"Environment: {settings.app.environment}")
    print(f"Database URL: {settings.get_database_url()}")
    print(f"Redis URL: {settings.get_redis_url()}")
    print(f"JWT Secret Key Length: {len(settings.jwt.secret_key)}")
    print(f"Rate Limit Endpoints: {len(settings.rate_limit.endpoint_limits)}")
    print(f"Log Level: {settings.logging.level}")
    print(f"App Name: {settings.app.name}")
    print(f"Debug Mode: {settings.app.debug}")
