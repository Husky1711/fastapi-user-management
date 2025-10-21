#!/usr/bin/env python3
"""
Security Logger
Specialized logger for security-related events and monitoring
"""

import logging
from utils.logger import BaseLogger
from typing import Optional

class SecurityLogger(BaseLogger):
    """Logger for security events"""
    
    def __init__(self):
        super().__init__('security')
    
    def rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str,
        limit_type: str,
        limit_value: int,
        current_count: int,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log rate limit exceeded"""
        self.warning(
            f"Rate limit exceeded: {limit_type} limit of {limit_value} exceeded (current: {current_count})",
            ip_address=ip_address,
            endpoint=endpoint,
            limit_type=limit_type,
            limit_value=limit_value,
            current_count=current_count,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="rate_limit_exceeded"
        )
    
    def suspicious_activity(
        self,
        activity_type: str,
        ip_address: str,
        user_id: Optional[int] = None,
        details: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log suspicious activity"""
        self.warning(
            f"Suspicious activity detected: {activity_type}",
            activity_type=activity_type,
            ip_address=ip_address,
            user_id=user_id,
            details=details,
            correlation_id=correlation_id,
            event_type="suspicious_activity"
        )
    
    def brute_force_attempt(
        self,
        ip_address: str,
        username: str,
        attempt_count: int,
        time_window_minutes: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log brute force attack attempt"""
        self.warning(
            f"Brute force attempt detected: {attempt_count} failed attempts for {username} from {ip_address} in {time_window_minutes} minutes",
            ip_address=ip_address,
            username=username,
            attempt_count=attempt_count,
            time_window_minutes=time_window_minutes,
            correlation_id=correlation_id,
            event_type="brute_force_attempt"
        )
    
    def ip_blocked(
        self,
        ip_address: str,
        reason: str,
        duration_minutes: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log IP blocking"""
        self.warning(
            f"IP address blocked: {ip_address} for {duration_minutes} minutes, reason: {reason}",
            ip_address=ip_address,
            reason=reason,
            duration_minutes=duration_minutes,
            correlation_id=correlation_id,
            event_type="ip_blocked"
        )
    
    def ip_unblocked(
        self,
        ip_address: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log IP unblocking"""
        self.info(
            f"IP address unblocked: {ip_address}",
            ip_address=ip_address,
            correlation_id=correlation_id,
            event_type="ip_unblocked"
        )
    
    def unauthorized_access_attempt(
        self,
        endpoint: str,
        method: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log unauthorized access attempt"""
        self.warning(
            f"Unauthorized access attempt: {method} {endpoint}",
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="unauthorized_access_attempt"
        )
    
    def privilege_escalation_attempt(
        self,
        user_id: int,
        ip_address: str,
        attempted_action: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log privilege escalation attempt"""
        self.warning(
            f"Privilege escalation attempt: user {user_id} attempted {attempted_action}",
            user_id=user_id,
            ip_address=ip_address,
            attempted_action=attempted_action,
            correlation_id=correlation_id,
            event_type="privilege_escalation_attempt"
        )
    
    def data_access_violation(
        self,
        user_id: int,
        resource_type: str,
        resource_id: str,
        ip_address: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log data access violation"""
        self.warning(
            f"Data access violation: user {user_id} attempted to access {resource_type} {resource_id}",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            correlation_id=correlation_id,
            event_type="data_access_violation"
        )
    
    def session_hijacking_attempt(
        self,
        user_id: int,
        original_ip: str,
        new_ip: str,
        user_agent: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log potential session hijacking"""
        self.warning(
            f"Potential session hijacking: user {user_id} session moved from {original_ip} to {new_ip}",
            user_id=user_id,
            original_ip=original_ip,
            new_ip=new_ip,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="session_hijacking_attempt"
        )
    
    def security_scan_detected(
        self,
        ip_address: str,
        scan_type: str,
        user_agent: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log security scan detection"""
        self.warning(
            f"Security scan detected: {scan_type} from {ip_address}",
            ip_address=ip_address,
            scan_type=scan_type,
            user_agent=user_agent,
            correlation_id=correlation_id,
            event_type="security_scan_detected"
        )
    
    def ddos_attack_detected(
        self,
        ip_address: str,
        request_count: int,
        time_window_seconds: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log DDoS attack detection"""
        self.critical(
            f"DDoS attack detected: {request_count} requests from {ip_address} in {time_window_seconds} seconds",
            ip_address=ip_address,
            request_count=request_count,
            time_window_seconds=time_window_seconds,
            correlation_id=correlation_id,
            event_type="ddos_attack_detected"
        )
    
    def configuration_change(
        self,
        setting_name: str,
        old_value: str,
        new_value: str,
        changed_by: int,
        ip_address: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log security configuration changes"""
        self.info(
            f"Security configuration changed: {setting_name} from '{old_value}' to '{new_value}'",
            setting_name=setting_name,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            ip_address=ip_address,
            correlation_id=correlation_id,
            event_type="configuration_change"
        )
    
    def security_alert(
        self,
        alert_type: str,
        severity: str,
        description: str,
        ip_address: Optional[str] = None,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log security alerts"""
        level = logging.CRITICAL if severity == "critical" else logging.ERROR if severity == "high" else logging.WARNING
        
        self._log_with_context(
            level,
            f"Security alert: {alert_type} - {description}",
            alert_type=alert_type,
            severity=severity,
            description=description,
            ip_address=ip_address,
            user_id=user_id,
            correlation_id=correlation_id,
            event_type="security_alert"
        )

# Create global instance
security_logger = SecurityLogger()
