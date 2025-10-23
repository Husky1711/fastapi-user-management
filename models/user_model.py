from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utils.database import Base

class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="organization")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    device_info = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)
    is_revoked = Column(Boolean, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="refresh_tokens")

# Update User model to include relationship
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)  # Hashed password
    email = Column(String(100), unique=True, index=True, nullable=False)
    status = Column(String(20), default="active")
    phone_number = Column(String(20), default="0000000000")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # New fields for role-based system
    role = Column(String(20), default="user")  # super_admin, admin, user
    organization_id = Column(Integer, ForeignKey("organizations.id"), default=1)
    
    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="users")

# New Production Tables (without foreign keys, using indexes)

class UserSession(Base):
    """User session tracking for security and analytics"""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    access_token_hash = Column(String(255), nullable=True)
    refresh_token_id = Column(Integer, nullable=True, index=True)
    device_fingerprint = Column(String(255), nullable=True, index=True)
    device_name = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet
    browser_name = Column(String(50), nullable=True)
    browser_version = Column(String(20), nullable=True)
    os_name = Column(String(50), nullable=True)
    os_version = Column(String(20), nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)
    country = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

class AuditLog(Base):
    """Comprehensive audit trail for compliance and security"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # login, logout, create_user, etc.
    event_category = Column(String(30), nullable=True, index=True)  # authentication, authorization, etc.
    resource_type = Column(String(50), nullable=True, index=True)  # user, organization, session, etc.
    resource_id = Column(Integer, nullable=True, index=True)
    action = Column(String(50), nullable=True, index=True)  # create, read, update, delete, login, logout
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    status = Column(String(20), nullable=True, index=True)  # success, failure, error
    error_message = Column(Text, nullable=True)
    log_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class PasswordHistory(Base):
    """Password history for security compliance"""
    __tablename__ = "password_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    changed_by = Column(Integer, nullable=True, index=True)  # user_id who changed it
    change_reason = Column(String(50), nullable=True, index=True)  # password_reset, password_change, admin_reset

class UserPermission(Base):
    """Granular permission management beyond roles"""
    __tablename__ = "user_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    permission_name = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)  # user, organization, session, etc.
    resource_id = Column(Integer, nullable=True, index=True)
    granted_by = Column(Integer, nullable=True, index=True)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)

class UserGroup(Base):
    """Group-based permissions and user management"""
    __tablename__ = "user_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True, index=True)

class UserGroupMembership(Base):
    """User membership in groups"""
    __tablename__ = "user_group_memberships"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    group_id = Column(Integer, nullable=False, index=True)
    added_by = Column(Integer, nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)

class ApiKey(Base):
    """API key management for programmatic access"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    key_name = Column(String(100), nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(20), nullable=False, index=True)  # First 8 chars for identification
    permissions = Column(JSON, nullable=True)  # Array of permissions
    rate_limit_per_minute = Column(Integer, default=100)
    rate_limit_per_hour = Column(Integer, default=1000)
    last_used_at = Column(DateTime(timezone=True), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_by = Column(Integer, nullable=False, index=True)