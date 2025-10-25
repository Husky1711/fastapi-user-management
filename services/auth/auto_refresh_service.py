#!/usr/bin/env python3
"""
Auto Refresh Token Service
Handles automatic token refresh for seamless user experience
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from sqlalchemy.orm import Session
from .refresh_token_service import RefreshTokenService
from .auth_service import AuthService
from utils.redis_config import RedisClient
from utils.loggers import auth_logger
from config.settings import settings

class AutoRefreshTokenService:
    """Service for automatic token refresh management"""
    
    def __init__(self):
        self.refresh_tasks: Dict[str, asyncio.Task] = {}
        self.refresh_callbacks: Dict[str, Callable] = {}
        self.refresh_intervals: Dict[str, int] = {}
    
    async def start_auto_refresh(
        self,
        user_id: int,
        refresh_token: str,
        callback: Optional[Callable] = None,
        refresh_interval_minutes: int = None
    ) -> str:
        """
        Start automatic token refresh for a user
        
        Args:
            user_id: User ID
            refresh_token: Current refresh token
            callback: Function to call with new tokens
            refresh_interval_minutes: How often to refresh (default: 80% of access token expiry)
            
        Returns:
            str: Task ID for managing this refresh cycle
        """
        if refresh_interval_minutes is None:
            # Refresh 1 minute before access token expires (5 min - 1 min = 4 min)
            refresh_interval_minutes = max(1, settings.jwt.access_token_expire_minutes - 1)
        
        task_id = f"refresh_{user_id}_{int(time.time())}"
        
        # Store callback and interval
        self.refresh_callbacks[task_id] = callback
        self.refresh_intervals[task_id] = refresh_interval_minutes
        
        # Start background refresh task
        task = asyncio.create_task(
            self._refresh_loop(task_id, user_id, refresh_token, refresh_interval_minutes)
        )
        self.refresh_tasks[task_id] = task
        
        auth_logger.info(
            f"Started auto refresh for user {user_id}",
            user_id=user_id,
            task_id=task_id,
            refresh_interval_minutes=refresh_interval_minutes,
            event_type="auto_refresh_started"
        )
        
        return task_id
    
    async def _refresh_loop(
        self,
        task_id: str,
        user_id: int,
        refresh_token: str,
        refresh_interval_minutes: int
    ):
        """Background loop for automatic token refresh"""
        try:
            while True:
                # Wait for refresh interval
                await asyncio.sleep(refresh_interval_minutes * 60)
                
                # Attempt to refresh token
                success, new_tokens = await self._attempt_refresh(user_id, refresh_token)
                
                if success:
                    refresh_token = new_tokens['refresh_token']
                    
                    # Call callback with new tokens
                    if task_id in self.refresh_callbacks:
                        callback = self.refresh_callbacks[task_id]
                        if callback:
                            await callback(new_tokens)
                    
                    auth_logger.info(
                        f"Auto refresh successful for user {user_id}",
                        user_id=user_id,
                        task_id=task_id,
                        event_type="auto_refresh_success"
                    )
                else:
                    auth_logger.warning(
                        f"Auto refresh failed for user {user_id}",
                        user_id=user_id,
                        task_id=task_id,
                        event_type="auto_refresh_failed"
                    )
                    break
                    
        except asyncio.CancelledError:
            auth_logger.info(
                f"Auto refresh cancelled for user {user_id}",
                user_id=user_id,
                task_id=task_id,
                event_type="auto_refresh_cancelled"
            )
        except Exception as e:
            auth_logger.error(
                f"Auto refresh error for user {user_id}: {str(e)}",
                user_id=user_id,
                task_id=task_id,
                error=str(e),
                event_type="auto_refresh_error"
            )
        finally:
            # Cleanup
            self._cleanup_task(task_id)
    
    async def _attempt_refresh(self, user_id: int, refresh_token: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Attempt to refresh tokens"""
        try:
            # This would need to be adapted to work with your database session
            # For now, we'll simulate the refresh process
            
            # In a real implementation, you'd:
            # 1. Get database session
            # 2. Call AuthService.refresh_access_token()
            # 3. Return new tokens
            
            # Simulate successful refresh
            return True, {
                'access_token': f"new_access_token_{int(time.time())}",
                'refresh_token': f"new_refresh_token_{int(time.time())}",
                'expires_in': settings.jwt.access_token_expire_minutes * 60
            }
            
        except Exception as e:
            auth_logger.error(
                f"Refresh attempt failed: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="refresh_attempt_failed"
            )
            return False, None
    
    def stop_auto_refresh(self, task_id: str) -> bool:
        """Stop automatic refresh for a specific task"""
        if task_id in self.refresh_tasks:
            task = self.refresh_tasks[task_id]
            task.cancel()
            self._cleanup_task(task_id)
            return True
        return False
    
    def stop_all_user_refresh(self, user_id: int) -> int:
        """Stop all auto refresh tasks for a user"""
        stopped_count = 0
        tasks_to_stop = []
        
        for task_id in self.refresh_tasks.keys():
            if f"refresh_{user_id}_" in task_id:
                tasks_to_stop.append(task_id)
        
        for task_id in tasks_to_stop:
            if self.stop_auto_refresh(task_id):
                stopped_count += 1
        
        auth_logger.info(
            f"Stopped {stopped_count} auto refresh tasks for user {user_id}",
            user_id=user_id,
            stopped_count=stopped_count,
            event_type="auto_refresh_stopped_all"
        )
        
        return stopped_count
    
    def _cleanup_task(self, task_id: str):
        """Clean up task resources"""
        if task_id in self.refresh_tasks:
            del self.refresh_tasks[task_id]
        if task_id in self.refresh_callbacks:
            del self.refresh_callbacks[task_id]
        if task_id in self.refresh_intervals:
            del self.refresh_intervals[task_id]
    
    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active refresh tasks"""
        active_tasks = {}
        for task_id, task in self.refresh_tasks.items():
            active_tasks[task_id] = {
                'task_running': not task.done(),
                'refresh_interval_minutes': self.refresh_intervals.get(task_id, 0),
                'has_callback': task_id in self.refresh_callbacks
            }
        return active_tasks
    
    async def refresh_now(self, user_id: int, refresh_token: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Manually trigger refresh now"""
        return await self._attempt_refresh(user_id, refresh_token)

# Global instance
auto_refresh_service = AutoRefreshTokenService()
