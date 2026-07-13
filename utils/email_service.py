"""
Email Service
Handles email sending with SMTP (Gmail support)
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from jinja2 import Environment, FileSystemLoader
import os
from utils.loggers import api_logger
from config.settings import settings


class EmailService:
    """Email service for sending emails via SMTP (Gmail)"""
    
    def __init__(self):
        # Gmail SMTP settings
        self.smtp_host = settings.email.smtp_host
        self.smtp_port = settings.email.smtp_port
        self.smtp_username = settings.email.smtp_username
        self.smtp_password = settings.email.smtp_password
        self.from_email = settings.email.from_email
        
        # Set up Jinja2 for email templates
        template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates', 'emails')
        self.env = Environment(loader=FileSystemLoader(template_dir))
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_text_content: str = None
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content
            plain_text_content: Plain text content (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not settings.email.enable_emails:
            api_logger.info(
                f"Email skipped (EMAIL__ENABLE_EMAILS=false): {subject}",
                to_email=to_email,
                subject=subject,
                event_type="email_skipped_disabled",
            )
            return False

        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = self.from_email
            message["To"] = to_email
            message["Subject"] = subject
            
            # Add plain text content
            if plain_text_content:
                text_part = MIMEText(plain_text_content, "plain")
                message.attach(text_part)
            
            # Add HTML content
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(self.smtp_username, self.smtp_password)
                smtp.send_message(message)
            
            api_logger.info(
                f"Email sent successfully to {to_email}",
                to_email=to_email,
                subject=subject,
                event_type="email_sent"
            )
            
            return True
            
        except Exception as e:
            api_logger.error(
                f"Email sending failed: {str(e)}",
                to_email=to_email,
                subject=subject,
                error=str(e),
                event_type="email_send_failed"
            )
            return False
    
    def render_template(self, template_name: str, context: dict) -> str:
        """
        Render email template with context
        
        Args:
            template_name: Name of template file
            context: Variables for template
            
        Returns:
            str: Rendered HTML content
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            api_logger.error(
                f"Template rendering failed: {str(e)}",
                template_name=template_name,
                error=str(e),
                event_type="email_template_error"
            )
            return ""
    
    def send_verification_email(self, to_email: str, verification_token: str, username: str) -> bool:
        """Send email verification email"""
        subject = "Verify Your Email Address"
        
        context = {
            "username": username,
            "verification_url": f"{settings.email.base_url}/verify/{verification_token}",
            "verification_token": verification_token
        }
        
        html_content = self.render_template("verification.html", context)
        plain_text = f"Hello {username},\n\nPlease verify your email by clicking this link: {context['verification_url']}"
        
        return self.send_email(to_email, subject, html_content, plain_text)
    
    def send_password_reset_email(self, to_email: str, reset_token: str, username: str) -> bool:
        """Send password reset email"""
        subject = "Password Reset Request"
        
        context = {
            "username": username,
            "reset_url": f"{settings.email.base_url}/reset-password/{reset_token}",
            "reset_token": reset_token
        }
        
        html_content = self.render_template("password_reset.html", context)
        plain_text = f"Hello {username},\n\nReset your password by clicking this link: {context['reset_url']}"
        
        return self.send_email(to_email, subject, html_content, plain_text)

    def send_invitation_email(
        self,
        to_email: str,
        invite_token: str,
        organization_name: str,
        role: str,
        invited_by: str,
    ) -> bool:
        """Send organization invitation email."""
        subject = f"You're invited to join {organization_name}"
        invite_url = f"{settings.email.base_url}/accept-invite/{invite_token}"
        context = {
            "organization_name": organization_name,
            "role": role,
            "invited_by": invited_by,
            "invite_url": invite_url,
            "invite_token": invite_token,
        }
        html_content = self.render_template("invitation.html", context)
        if not html_content:
            html_content = (
                f"<p>You have been invited by <strong>{invited_by}</strong> "
                f"to join <strong>{organization_name}</strong> as <strong>{role}</strong>.</p>"
                f'<p><a href="{invite_url}">Accept invitation</a></p>'
            )
        plain_text = (
            f"You have been invited by {invited_by} to join {organization_name} "
            f"as {role}. Accept: {invite_url}"
        )
        return self.send_email(to_email, subject, html_content, plain_text)
    
    def send_welcome_email(self, to_email: str, username: str, temp_password: str = None) -> bool:
        """Send welcome email to new user"""
        subject = "Welcome to FastAPI User Management System"
        
        context = {
            "username": username,
            "temp_password": temp_password,
            "login_url": f"{settings.email.base_url}/login"
        }
        
        html_content = self.render_template("welcome.html", context)
        plain_text = f"Welcome {username}!\n\nYour account has been created successfully."
        if temp_password:
            plain_text += f"\nTemporary password: {temp_password}"
        
        return self.send_email(to_email, subject, html_content, plain_text)
    
    def send_security_alert_email(self, to_email: str, username: str, alert_type: str, details: str) -> bool:
        """Send security alert email"""
        subject = f"Security Alert: {alert_type}"
        
        context = {
            "username": username,
            "alert_type": alert_type,
            "details": details
        }
        
        html_content = self.render_template("security_alert.html", context)
        plain_text = f"Security Alert for {username}: {alert_type}\n\n{details}"
        
        return self.send_email(to_email, subject, html_content, plain_text)


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get email service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


# Helper function for synchronous use
def send_email_sync(
    to_email: str,
    subject: str,
    html_content: str,
    plain_text_content: str = None
) -> bool:
    """Synchronous wrapper for sending email"""
    email_service = get_email_service()
    return email_service.send_email(to_email, subject, html_content, plain_text_content)
