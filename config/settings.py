#!/usr/bin/env python3
"""
Centralized Configuration Management
Using Pydantic Settings for type-safe configuration
"""

import os
from typing import Dict, Any, Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pathlib import Path

# Codespaces / local Docker MySQL (see docker-compose.codespaces.yml)
CODESPACES_DATABASE_URL = (
    "mysql+pymysql://fastapi:fastapi@localhost:3306/fastapi_users"
)

# Known insecure default — allowed only in development; rejected in production startup.
INSECURE_DEV_JWT_SECRET = (
    "your-super-secret-key-change-this-in-production-must-be-at-least-32-chars"
)

DEFAULT_DATABASE_URL = CODESPACES_DATABASE_URL


class DatabaseSettings(BaseSettings):
    """Database configuration settings.

    Env vars (prefer these — ``env_prefix=DB_``)::

        DB_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT,
        DB_POOL_RECYCLE, DB_STATEMENT_TIMEOUT_SECONDS, DB_ECHO

    Nested form also works when set on the root Settings object::

        DATABASE__POOL_SIZE, DATABASE__MAX_OVERFLOW, ...

    (``DB__POOL_SIZE`` with a double underscore does **not** bind — that is a
    common misread of the nested delimiter.)
    """

    url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", CODESPACES_DATABASE_URL),
        description="Database connection URL",
    )
    echo: bool = Field(False, description="Enable SQLAlchemy echo for debugging")
    pool_size: int = Field(
        20,
        ge=1,
        le=200,
        description="SQLAlchemy pool size per process (tune: replicas × workers × pool)",
    )
    max_overflow: int = Field(
        40,
        ge=0,
        le=400,
        description="Extra connections above pool_size under burst",
    )
    pool_timeout: int = Field(
        30,
        ge=1,
        le=300,
        description="Seconds to wait for a connection from the pool",
    )
    pool_recycle: int = Field(
        3600,
        ge=60,
        le=86400,
        description="Seconds before a pooled connection is recycled",
    )
    statement_timeout_seconds: int = Field(
        30,
        ge=1,
        le=600,
        description="Per-statement query timeout in seconds (MySQL MAX_EXECUTION_TIME / Postgres statement_timeout)",
    )

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
    circuit_failure_threshold: int = Field(
        3,
        ge=1,
        le=50,
        description="Consecutive failures before opening the Redis circuit",
    )
    circuit_cooldown_seconds: int = Field(
        30,
        ge=1,
        le=600,
        description="Base cooldown when the Redis circuit opens (doubles with backoff)",
    )
    circuit_max_cooldown_seconds: int = Field(
        300,
        ge=1,
        le=3600,
        description="Maximum circuit-open cooldown under exponential backoff",
    )

    class Config:
        env_prefix = "REDIS_"

class JWTSettings(BaseSettings):
    """JWT configuration settings"""
    secret_key: str = Field(INSECURE_DEV_JWT_SECRET, description="JWT secret key")
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

class SessionSettings(BaseSettings):
    """Session management configuration settings"""
    
    # Default session strategy
    default_strategy: str = Field("replace_all", description="Default session management strategy")
    
    # Available strategies
    available_strategies: List[str] = Field(
        default=["allow_multiple", "replace_all", "replace_same_device", "deny_if_exists", "limit_sessions"],
        description="Available session management strategies"
    )
    
    # Session limits
    max_sessions_per_user: int = Field(5, description="Maximum concurrent auth sessions (refresh tokens) per user")
    max_sessions_per_device: int = Field(2, description="Maximum sessions per device")
    
    # Analytics / idle session timeout (refresh TTL is jwt.refresh_token_expire_days only)
    session_timeout_hours: int = Field(24, description="Analytics session timeout in hours")
    
    # Auto cleanup settings
    auto_cleanup_enabled: bool = Field(True, description="Enable automatic session cleanup")
    cleanup_interval_hours: int = Field(1, description="Session cleanup interval in hours")
    cleanup_expired_sessions: bool = Field(True, description="Clean up expired sessions")
    cleanup_inactive_sessions: bool = Field(True, description="Clean up inactive sessions")
    
    # Security settings
    allow_multiple_sessions: bool = Field(True, description="Allow multiple sessions per user")
    require_device_confirmation: bool = Field(False, description="Require device confirmation for new sessions")
    track_device_changes: bool = Field(True, description="Track device changes for security")
    alert_on_suspicious_activity: bool = Field(True, description="Alert on suspicious session activity")
    
    # User experience settings
    show_session_warning: bool = Field(True, description="Show warning when approaching session limit")
    allow_user_session_management: bool = Field(True, description="Allow users to manage their sessions")
    remember_device: bool = Field(True, description="Remember device for easier login")
    
    # Environment-specific overrides
    development_strategy: str = Field("allow_multiple", description="Strategy for development environment")
    production_strategy: str = Field("replace_all", description="Strategy for production environment")
    staging_strategy: str = Field("limit_sessions", description="Strategy for staging environment")
    
    @field_validator('default_strategy')
    @classmethod
    def validate_strategy(cls, v):
        valid_strategies = ["allow_multiple", "replace_all", "replace_same_device", "deny_if_exists", "limit_sessions"]
        if v not in valid_strategies:
            raise ValueError(f'Strategy must be one of: {valid_strategies}')
        return v
    
    @field_validator('max_sessions_per_user')
    @classmethod
    def validate_max_sessions(cls, v):
        if v < 1 or v > 20:
            raise ValueError('Max sessions per user must be between 1 and 20')
        return v
    
    class Config:
        env_prefix = "SESSION_"

class PasswordPolicySettings(BaseSettings):
    """Password policy configuration settings"""
    
    # Password history settings
    enable_password_history: bool = Field(True, description="Enable password history tracking")
    password_history_limit: int = Field(5, description="Number of recent passwords to prevent reuse")
    password_history_retention_days: int = Field(365, description="Days to retain password history")
    
    # Password complexity settings
    min_password_length: int = Field(8, description="Minimum password length")
    max_password_length: int = Field(100, description="Maximum password length")
    require_uppercase: bool = Field(True, description="Require uppercase letters")
    require_lowercase: bool = Field(True, description="Require lowercase letters")
    require_digits: bool = Field(True, description="Require digits")
    require_special_chars: bool = Field(False, description="Require special characters")
    
    # Password age settings
    max_password_age_days: int = Field(90, description="Maximum password age in days")
    password_expiry_warning_days: int = Field(7, description="Days before expiry to show warning")
    enforce_max_password_age: bool = Field(
        False,
        description="Reject login when password_changed_at exceeds max_password_age_days",
    )
    allow_legacy_sha256_hashes: bool = Field(
        True,
        description=(
            "Accept legacy SHA-256 password hashes at login and auto-rehash to bcrypt. "
            "Set false after running scripts/ensure_bcrypt_seed_passwords.py / cutover "
            "(PASSWORD__ALLOW_LEGACY_SHA256_HASHES=false)."
        ),
    )

    # Lockout lives under SecuritySettings (single source of truth).
    
    @field_validator('password_history_limit')
    @classmethod
    def validate_history_limit(cls, v):
        if v < 1 or v > 20:
            raise ValueError('Password history limit must be between 1 and 20')
        return v
    
    @field_validator('min_password_length')
    @classmethod
    def validate_min_length(cls, v):
        if v < 6 or v > 50:
            raise ValueError('Minimum password length must be between 6 and 50')
        return v
    
    @field_validator('max_password_age_days')
    @classmethod
    def validate_max_age(cls, v):
        if v < 30 or v > 365:
            raise ValueError('Maximum password age must be between 30 and 365 days')
        return v
    
    class Config:
        env_prefix = "PASSWORD_"

class RateLimitSettings(BaseSettings):
    """Rate limiting configuration settings"""
    
    # Endpoint-specific rate limits
    endpoint_limits: Dict[str, Dict[str, int]] = Field(
        default={
            "users_list": {"minute": 10, "hour": 100},
            "user_detail": {"minute": 50, "hour": 500},
            "profile": {"minute": 100, "hour": 1000},
            "profile_update": {"minute": 30, "hour": 300},
            "dashboard": {"minute": 100, "hour": 1000},
            "admin": {"minute": 100, "hour": 1000},
            "super_admin": {"minute": 200, "hour": 2000},
            "sessions": {"minute": 30, "hour": 300},
            "session_revoke": {"minute": 10, "hour": 100},
            "login": {"minute": 50, "hour": 500},
            "refresh": {"minute": 50, "hour": 500},
            "signup": {"minute": 10, "hour": 100},
            "password_change": {"minute": 10, "hour": 100},
            "password_reset": {"minute": 5, "hour": 50},
            "password_reset_request": {"minute": 5, "hour": 50},
            "password_reset_confirm": {"minute": 10, "hour": 100},
            "email_verify": {"minute": 20, "hour": 100},
            "email_resend_verification": {"minute": 5, "hour": 20},
            "2fa_enable": {"minute": 5, "hour": 20},
            "2fa_verify": {"minute": 10, "hour": 50},
            "2fa_disable": {"minute": 5, "hour": 20},
            "2fa_status": {"minute": 30, "hour": 300},
        },
        description="Rate limits for specific endpoints"
    )

    # Per-email buckets (password-reset email bombing protection)
    email_limits: Dict[str, Dict[str, int]] = Field(
        default={
            "password_reset_request": {"minute": 3, "hour": 10},
        },
        description="Rate limits keyed by normalized email for sensitive unauthenticated flows",
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
    enable_email_limits: bool = Field(True, description="Enable per-email rate limits")
    
    class Config:
        env_prefix = "RATE_LIMIT_"

class LoggingSettings(BaseSettings):
    """Logging configuration settings"""
    level: str = Field("INFO", description="Logging level")
    log_dir: str = Field("logs", description="Log directory")
    max_file_size: int = Field(10 * 1024 * 1024, description="Max log file size in bytes")  # 10MB
    backup_count: int = Field(5, description="Number of backup files to keep")
    enable_console: bool = Field(True, description="Enable console logging")
    enable_file: bool = Field(
        True,
        description="Enable file logging (auto-disabled in production unless LOG__FORCE_FILE=true)",
    )
    force_file: bool = Field(
        False,
        description="Force file handlers even in production (not recommended for containers)",
    )
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
    cors_origins: list = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ],
        description="CORS allowed origins (must be explicit when using credentials)",
    )
    enable_https_redirect: bool = Field(False, description="Enable HTTPS redirect")
    session_timeout_minutes: int = Field(30, description="Session timeout in minutes")
    max_login_attempts: int = Field(5, description="Maximum login attempts")
    lockout_duration_minutes: int = Field(15, description="Account lockout duration")
    allow_public_signup: bool = Field(
        False,
        description="Allow unauthenticated POST /api/v1/signup (disable in production)",
    )
    require_email_verification: bool = Field(
        False,
        description="Reject login until users.email_verified_at is set",
    )
    allow_debug_auth: bool = Field(
        False,
        description="Enable POST /api/v1/debug-login and debug-refresh (disable in production)",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            import json
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [origin.strip() for origin in text.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_with_credentials(cls, value: list) -> list:
        """Browsers reject credentialed requests when Allow-Origin is *."""
        if "*" in value:
            filtered = [origin for origin in value if origin != "*"]
            return filtered or [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        return value
    
    class Config:
        env_prefix = "SECURITY_"


class AuthCookieSettings(BaseSettings):
    """httpOnly refresh-token cookie settings for browser clients."""
    use_httponly_refresh: bool = Field(
        True, description="Set refresh token in httpOnly cookie"
    )
    legacy_json_refresh: bool = Field(
        True,
        description="Also return refresh_token in JSON during transition (disable in prod)",
    )
    name: str = Field("refresh_token", description="Refresh cookie name")
    path: str = Field("/api/v1", description="Cookie path")
    domain: Optional[str] = Field(
        None,
        description="Cookie domain (e.g. .example.com); empty for host-only",
    )
    samesite: str = Field("lax", description="SameSite policy: lax, strict, or none")
    secure: bool = Field(
        False,
        description="Secure cookie flag (enable in staging/production HTTPS)",
    )

    @field_validator("samesite")
    @classmethod
    def validate_samesite(cls, v: str) -> str:
        allowed = {"lax", "strict", "none"}
        value = v.lower()
        if value not in allowed:
            raise ValueError(f"SameSite must be one of: {allowed}")
        return value

    class Config:
        env_prefix = "AUTH_COOKIE__"

class EmailSettings(BaseSettings):
    """Email configuration settings"""
    smtp_host: str = Field("", description="SMTP server host")
    smtp_port: int = Field(587, description="SMTP server port")
    smtp_username: str = Field("", description="SMTP username")
    smtp_password: str = Field("", description="SMTP password")
    from_email: str = Field("", description="From email address")
    base_url: str = Field(
        "http://localhost:5173",
        description="Public frontend base URL for email links (password reset, verify)",
    )
    enable_emails: bool = Field(False, description="Enable email sending")
    
    class Config:
        env_prefix = "EMAIL_"

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
    enable_retention_job: bool = Field(
        False,
        description="Run background retention cleanup loop (sessions, tokens, history)",
    )
    retention_interval_minutes: int = Field(
        60,
        ge=5,
        le=1440,
        description="Minutes between retention cleanup runs when enabled",
    )
    login_attempts_retention_days: int = Field(
        90,
        ge=7,
        le=365,
        description="Days to retain login_attempts rows before purge",
    )
    audit_logs_retention_days: int = Field(
        365,
        ge=30,
        le=2555,
        description="Days to retain audit_logs rows before purge (partitioning is separate)",
    )
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production']
        if v.lower() not in valid_envs:
            raise ValueError(f'Environment must be one of: {valid_envs}')
        return v.lower()
    
    class Config:
        env_prefix = "APP_"


class OtellSettings(BaseSettings):
    """Optional OpenTelemetry export (install requirements-otel.txt)."""

    enabled: bool = Field(
        False,
        description="Instrument FastAPI with OpenTelemetry when OTEL packages are installed",
    )
    service_name: str = Field(
        "fastapi-user-management",
        description="OTEL resource service.name",
    )
    exporter_otlp_endpoint: Optional[str] = Field(
        None,
        description="OTLP HTTP/gRPC endpoint (also honor OTEL_EXPORTER_OTLP_ENDPOINT)",
    )

    class Config:
        env_prefix = "OTEL_"


class Settings(BaseSettings):
    """Main settings class that combines all configuration sections"""
    
    # Configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    password_policy: PasswordPolicySettings = Field(default_factory=PasswordPolicySettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    auth_cookie: AuthCookieSettings = Field(default_factory=AuthCookieSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    otel: OtellSettings = Field(default_factory=OtellSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        extra = "ignore"  # Ignore extra fields from environment
        
        # Allow nested env vars
        env_nested_delimiter = "__"

    def model_post_init(self, __context: Any) -> None:
        """Append GitHub Codespaces public origins for browser clients."""
        codespace = os.getenv("CODESPACE_NAME")
        if not codespace:
            return
        for port in (5173, 9000):
            origin = f"https://{codespace}-{port}.app.github.dev"
            if origin not in self.security.cors_origins:
                self.security.cors_origins.append(origin)
    
    def get_database_url(self) -> str:
        """Get database URL with validation"""
        return self.database.url
    
    def get_redis_url(self) -> str:
        """Get Redis URL"""
        password_part = f":{self.redis.password}@" if self.redis.password else ""
        return f"redis://{password_part}{self.redis.host}:{self.redis.port}/{self.redis.db}"
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.app.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.app.environment.lower() == "development"

    def validate_production_config(self) -> None:
        """Fail fast when production is configured with unsafe defaults."""
        if not self.is_production():
            return

        errors: List[str] = []
        if self.jwt.secret_key == INSECURE_DEV_JWT_SECRET:
            errors.append("JWT__SECRET_KEY must be set to a strong unique value in production")
        if self.security.allow_debug_auth:
            errors.append("SECURITY__ALLOW_DEBUG_AUTH must be false in production")
        if not self.is_development() and self.security.allow_debug_auth:
            errors.append("SECURITY__ALLOW_DEBUG_AUTH must be false outside development")
        if self.security.allow_public_signup:
            errors.append("SECURITY__ALLOW_PUBLIC_SIGNUP must be false in production")
        if self.auth_cookie.legacy_json_refresh:
            errors.append("AUTH_COOKIE__LEGACY_JSON_REFRESH should be false in production")
        if not self.auth_cookie.secure:
            errors.append("AUTH_COOKIE__SECURE must be true in production (HTTPS required)")
        if self.rate_limit.fail_open:
            errors.append(
                "RATE_LIMIT__FAIL_OPEN must be false in production "
                "(Redis is a hard dependency for rate limiting)"
            )
        if self.password_policy.allow_legacy_sha256_hashes:
            errors.append(
                "PASSWORD__ALLOW_LEGACY_SHA256_HASHES must be false in production "
                "(run scripts/ensure_bcrypt_seed_passwords.py --report first)"
            )

        if errors:
            raise ValueError(
                "Production configuration validation failed:\n"
                + "\n".join(f"  - {item}" for item in errors)
            )
    
    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return {
            "level": self.logging.level,
            "log_dir": self.logging.log_dir,
            "max_file_size": self.logging.max_file_size,
            "backup_count": self.logging.backup_count,
            "enable_console": self.logging.enable_console,
            "enable_file": self.logging.enable_file,
            "force_file": self.logging.force_file,
            "enable_json": self.logging.enable_json,
            "rotation_enabled": self.logging.rotation_enabled,
            "rotation_schedule": self.logging.rotation_schedule,
            "retention_days": self.logging.retention_days,
            "environment": self.app.environment,
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
    # Local config smoke check only — never log secrets or secret lengths.
    print("Configuration loaded successfully!")
    print(f"Environment: {settings.app.environment}")
    print(f"Redis host: {settings.redis.host}:{settings.redis.port}")
    print(f"Rate Limit Endpoints: {len(settings.rate_limit.endpoint_limits)}")
    print(f"Log Level: {settings.logging.level}")
    print(f"App Name: {settings.app.name}")
    print(f"Debug Mode: {settings.app.debug}")
    print(f"JWT secret configured: {bool(settings.jwt.secret_key)}")
    print(f"Database dialect: {settings.database.url.split(':', 1)[0]}")
