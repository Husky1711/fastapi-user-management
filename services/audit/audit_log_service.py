from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user_model import AuditLog, User
from utils.loggers import auth_logger
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json
import uuid

class AuditLogService:
    """Service for comprehensive audit logging and compliance tracking"""
    
    @staticmethod
    def create_audit_log(
        db: Session,
        event_type: str,
        event_category: str = None,
        resource_type: str = None,
        resource_id: int = None,
        action: str = None,
        user_id: int = None,
        organization_id: int = None,
        old_values: Dict[str, Any] = None,
        new_values: Dict[str, Any] = None,
        ip_address: str = None,
        user_agent: str = None,
        request_id: str = None,
        correlation_id: str = None,
        status: str = "success",
        error_message: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a comprehensive audit log entry
        
        Args:
            db: Database session
            event_type: Type of event (login, logout, create_user, etc.)
            event_category: Category of event (authentication, authorization, etc.)
            resource_type: Type of resource affected (user, organization, etc.)
            resource_id: ID of the resource affected
            action: Action performed (create, read, update, delete, login, logout)
            user_id: ID of the user performing the action
            organization_id: ID of the organization
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            ip_address: IP address of the request
            user_agent: User agent string
            request_id: Unique request identifier
            correlation_id: Correlation ID for tracing
            status: Status of the operation (success, failure, error)
            error_message: Error message if applicable
            metadata: Additional metadata
            
        Returns:
            Dictionary with audit log creation result
        """
        try:
            # Generate correlation ID if not provided
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
            
            # Generate request ID if not provided
            if not request_id:
                request_id = str(uuid.uuid4())
            
            # Create audit log entry
            audit_entry = AuditLog(
                user_id=user_id,
                organization_id=organization_id,
                event_type=event_type,
                event_category=event_category,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                correlation_id=correlation_id,
                status=status,
                error_message=error_message,
                log_metadata=metadata,
                created_at=datetime.utcnow()
            )
            
            db.add(audit_entry)
            db.commit()
            db.refresh(audit_entry)
            
            # Log the audit creation
            auth_logger.info(
                f"Audit log created: {event_type} - {action}",
                audit_id=audit_entry.id,
                event_type=event_type,
                event_category=event_category,
                user_id=user_id,
                organization_id=organization_id,
                status=status,
                correlation_id=correlation_id,
                event_type_audit="audit_log_created"
            )
            
            return {
                "success": True,
                "audit_id": audit_entry.id,
                "correlation_id": correlation_id,
                "request_id": request_id,
                "message": "Audit log created successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error creating audit log: {str(e)}",
                event_type=event_type,
                action=action,
                user_id=user_id,
                error=str(e),
                event_type_audit="audit_log_creation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to create audit log: {str(e)}"
            }
    
    @staticmethod
    def log_user_action(
        db: Session,
        user_id: int,
        action: str,
        resource_type: str = None,
        resource_id: int = None,
        old_values: Dict[str, Any] = None,
        new_values: Dict[str, Any] = None,
        ip_address: str = None,
        user_agent: str = None,
        request_id: str = None,
        correlation_id: str = None,
        status: str = "success",
        error_message: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Log a user action with automatic event categorization
        
        Args:
            db: Database session
            user_id: ID of the user performing the action
            action: Action performed
            resource_type: Type of resource affected
            resource_id: ID of the resource affected
            old_values: Previous values
            new_values: New values
            ip_address: IP address
            user_agent: User agent string
            request_id: Request ID
            correlation_id: Correlation ID
            status: Status of operation
            error_message: Error message
            metadata: Additional metadata
            
        Returns:
            Dictionary with audit log result
        """
        try:
            # Get user to determine organization
            user = db.query(User).filter(User.id == user_id).first()
            organization_id = user.organization_id if user else None
            
            # Determine event category based on action
            event_category = AuditLogService._get_event_category(action)
            
            # Determine event type based on action and resource
            event_type = AuditLogService._get_event_type(action, resource_type)
            
            return AuditLogService.create_audit_log(
                db=db,
                event_type=event_type,
                event_category=event_category,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                user_id=user_id,
                organization_id=organization_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                correlation_id=correlation_id,
                status=status,
                error_message=error_message,
                metadata=metadata
            )
            
        except Exception as e:
            auth_logger.error(
                f"Error logging user action: {str(e)}",
                user_id=user_id,
                action=action,
                error=str(e),
                event_type_audit="user_action_logging_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to log user action: {str(e)}"
            }
    
    @staticmethod
    def log_authentication_event(
        db: Session,
        event_type: str,
        user_id: int = None,
        username: str = None,
        email: str = None,
        ip_address: str = None,
        user_agent: str = None,
        request_id: str = None,
        correlation_id: str = None,
        status: str = "success",
        error_message: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Log authentication-related events
        
        Args:
            db: Database session
            event_type: Type of auth event (login, logout, login_failed, etc.)
            user_id: User ID
            username: Username
            email: Email address
            ip_address: IP address
            user_agent: User agent
            request_id: Request ID
            correlation_id: Correlation ID
            status: Status
            error_message: Error message
            metadata: Additional metadata
            
        Returns:
            Dictionary with audit log result
        """
        try:
            # Get user info if user_id provided
            organization_id = None
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    organization_id = user.organization_id
                    username = username or user.username
                    email = email or user.email
            
            # Add auth-specific metadata
            auth_metadata = {
                "username": username,
                "email": email,
                **(metadata or {})
            }
            
            return AuditLogService.create_audit_log(
                db=db,
                event_type=event_type,
                event_category="authentication",
                resource_type="user",
                resource_id=user_id,
                action=event_type,
                user_id=user_id,
                organization_id=organization_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                correlation_id=correlation_id,
                status=status,
                error_message=error_message,
                metadata=auth_metadata
            )
            
        except Exception as e:
            auth_logger.error(
                f"Error logging authentication event: {str(e)}",
                event_type=event_type,
                user_id=user_id,
                error=str(e),
                event_type_audit="auth_event_logging_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to log authentication event: {str(e)}"
            }
    
    @staticmethod
    def log_security_event(
        db: Session,
        event_type: str,
        user_id: int = None,
        organization_id: int = None,
        resource_type: str = None,
        resource_id: int = None,
        ip_address: str = None,
        user_agent: str = None,
        request_id: str = None,
        correlation_id: str = None,
        status: str = "success",
        error_message: str = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Log security-related events
        
        Args:
            db: Database session
            event_type: Type of security event
            user_id: User ID
            organization_id: Organization ID
            resource_type: Resource type
            resource_id: Resource ID
            ip_address: IP address
            user_agent: User agent
            request_id: Request ID
            correlation_id: Correlation ID
            status: Status
            error_message: Error message
            metadata: Additional metadata
            
        Returns:
            Dictionary with audit log result
        """
        try:
            return AuditLogService.create_audit_log(
                db=db,
                event_type=event_type,
                event_category="security",
                resource_type=resource_type,
                resource_id=resource_id,
                action=event_type,
                user_id=user_id,
                organization_id=organization_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                correlation_id=correlation_id,
                status=status,
                error_message=error_message,
                metadata=metadata
            )
            
        except Exception as e:
            auth_logger.error(
                f"Error logging security event: {str(e)}",
                event_type=event_type,
                user_id=user_id,
                error=str(e),
                event_type_audit="security_event_logging_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to log security event: {str(e)}"
            }
    
    @staticmethod
    def get_audit_logs(
        db: Session,
        user_id: int = None,
        organization_id: int = None,
        event_type: str = None,
        event_category: str = None,
        resource_type: str = None,
        status: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Retrieve audit logs with filtering
        
        Args:
            db: Database session
            user_id: Filter by user ID
            organization_id: Filter by organization ID
            event_type: Filter by event type
            event_category: Filter by event category
            resource_type: Filter by resource type
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of records
            offset: Number of records to skip
            
        Returns:
            Dictionary with audit logs
        """
        try:
            query = db.query(AuditLog)
            
            # Apply filters
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            if organization_id:
                query = query.filter(AuditLog.organization_id == organization_id)
            if event_type:
                query = query.filter(AuditLog.event_type == event_type)
            if event_category:
                query = query.filter(AuditLog.event_category == event_category)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            if status:
                query = query.filter(AuditLog.status == status)
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            # Get total count
            total_count = query.count()
            
            # Apply pagination and ordering
            audit_logs = query.order_by(AuditLog.created_at.desc())\
                .offset(offset)\
                .limit(limit)\
                .all()
            
            # Format results
            logs_data = []
            for log in audit_logs:
                logs_data.append({
                    "id": log.id,
                    "user_id": log.user_id,
                    "organization_id": log.organization_id,
                    "event_type": log.event_type,
                    "event_category": log.event_category,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "action": log.action,
                    "old_values": log.old_values,
                    "new_values": log.new_values,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "request_id": log.request_id,
                    "correlation_id": log.correlation_id,
                    "status": log.status,
                    "error_message": log.error_message,
                    "metadata": log.log_metadata,
                    "created_at": log.created_at.isoformat()
                })
            
            return {
                "success": True,
                "logs": logs_data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error retrieving audit logs: {str(e)}",
                user_id=user_id,
                organization_id=organization_id,
                error=str(e),
                event_type_audit="audit_log_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to retrieve audit logs: {str(e)}"
            }
    
    @staticmethod
    def get_audit_statistics(
        db: Session,
        organization_id: int = None,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Get audit statistics
        
        Args:
            db: Database session
            organization_id: Filter by organization
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            Dictionary with audit statistics
        """
        try:
            query = db.query(AuditLog)
            
            if organization_id:
                query = query.filter(AuditLog.organization_id == organization_id)
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            # Get total count
            total_logs = query.count()
            
            # Get counts by event type
            event_types = db.query(AuditLog.event_type, func.count(AuditLog.id))\
                .group_by(AuditLog.event_type)\
                .all()
            
            # Get counts by status
            status_counts = db.query(AuditLog.status, func.count(AuditLog.id))\
                .group_by(AuditLog.status)\
                .all()
            
            # Get counts by category
            category_counts = db.query(AuditLog.event_category, func.count(AuditLog.id))\
                .group_by(AuditLog.event_category)\
                .all()
            
            return {
                "success": True,
                "statistics": {
                    "total_logs": total_logs,
                    "event_types": dict(event_types),
                    "status_counts": dict(status_counts),
                    "category_counts": dict(category_counts)
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting audit statistics: {str(e)}",
                organization_id=organization_id,
                error=str(e),
                event_type_audit="audit_statistics_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get audit statistics: {str(e)}"
            }
    
    @staticmethod
    def _get_event_category(action: str) -> str:
        """Determine event category based on action"""
        auth_actions = ["login", "logout", "login_failed", "password_change", "password_reset"]
        security_actions = ["account_locked", "suspicious_activity", "rate_limit_exceeded"]
        data_actions = ["create", "read", "update", "delete"]
        
        if action in auth_actions:
            return "authentication"
        elif action in security_actions:
            return "security"
        elif action in data_actions:
            return "data_access"
        else:
            return "general"
    
    @staticmethod
    def _get_event_type(action: str, resource_type: str = None) -> str:
        """Determine event type based on action and resource"""
        if action == "create" and resource_type:
            return f"create_{resource_type}"
        elif action == "update" and resource_type:
            return f"update_{resource_type}"
        elif action == "delete" and resource_type:
            return f"delete_{resource_type}"
        else:
            return action
