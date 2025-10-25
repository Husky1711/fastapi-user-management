from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user_model import UserGroup, UserGroupMembership, User, UserPermission
from utils.loggers import auth_logger
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

class UserGroupService:
    """Service for user group management"""
    
    @staticmethod
    def create_group(
        db: Session,
        organization_id: int,
        name: str,
        description: str = None,
        created_by: int = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a new user group
        
        Args:
            db: Database session
            organization_id: ID of the organization
            name: Name of the group
            description: Description of the group
            created_by: ID of the user creating the group
            metadata: Additional metadata
            
        Returns:
            Dictionary with group creation result
        """
        try:
            # Check if group name already exists in organization
            existing = db.query(UserGroup)\
                .filter(UserGroup.organization_id == organization_id)\
                .filter(UserGroup.name == name)\
                .filter(UserGroup.is_active == True)\
                .first()
            
            if existing:
                return {
                    "success": False,
                    "error": "Group name already exists in this organization"
                }
            
            # Create new group
            group = UserGroup(
                organization_id=organization_id,
                name=name,
                description=description,
                created_by=created_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True
            )
            
            db.add(group)
            db.commit()
            db.refresh(group)
            
            # Log group creation
            auth_logger.info(
                f"User group created: {name}",
                group_id=group.id,
                organization_id=organization_id,
                created_by=created_by,
                event_type="group_created"
            )
            
            return {
                "success": True,
                "group_id": group.id,
                "group": {
                    "id": group.id,
                    "name": group.name,
                    "description": group.description,
                    "organization_id": group.organization_id,
                    "created_by": group.created_by,
                    "created_at": group.created_at.isoformat(),
                    "updated_at": group.updated_at.isoformat(),
                    "is_active": group.is_active
                },
                "message": f"Group '{name}' created successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error creating user group: {str(e)}",
                organization_id=organization_id,
                name=name,
                error=str(e),
                event_type="group_creation_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to create group: {str(e)}"
            }
    
    @staticmethod
    def update_group(
        db: Session,
        group_id: int,
        name: str = None,
        description: str = None,
        updated_by: int = None
    ) -> Dict[str, Any]:
        """
        Update a user group
        
        Args:
            db: Database session
            group_id: ID of the group to update
            name: New name (optional)
            description: New description (optional)
            updated_by: ID of the user updating the group
            
        Returns:
            Dictionary with update result
        """
        try:
            # Find the group
            group = db.query(UserGroup)\
                .filter(UserGroup.id == group_id)\
                .filter(UserGroup.is_active == True)\
                .first()
            
            if not group:
                return {
                    "success": False,
                    "error": "Group not found or inactive"
                }
            
            # Update fields
            if name is not None:
                # Check if new name already exists
                existing = db.query(UserGroup)\
                    .filter(UserGroup.organization_id == group.organization_id)\
                    .filter(UserGroup.name == name)\
                    .filter(UserGroup.id != group_id)\
                    .filter(UserGroup.is_active == True)\
                    .first()
                
                if existing:
                    return {
                        "success": False,
                        "error": "Group name already exists in this organization"
                    }
                
                group.name = name
            
            if description is not None:
                group.description = description
            
            group.updated_at = datetime.utcnow()
            
            db.commit()
            
            # Log group update
            auth_logger.info(
                f"User group updated: {group.name}",
                group_id=group_id,
                updated_by=updated_by,
                event_type="group_updated"
            )
            
            return {
                "success": True,
                "message": f"Group '{group.name}' updated successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error updating user group: {str(e)}",
                group_id=group_id,
                error=str(e),
                event_type="group_update_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to update group: {str(e)}"
            }
    
    @staticmethod
    def delete_group(
        db: Session,
        group_id: int,
        deleted_by: int = None
    ) -> Dict[str, Any]:
        """
        Delete a user group (soft delete)
        
        Args:
            db: Database session
            group_id: ID of the group to delete
            deleted_by: ID of the user deleting the group
            
        Returns:
            Dictionary with deletion result
        """
        try:
            # Find the group
            group = db.query(UserGroup)\
                .filter(UserGroup.id == group_id)\
                .filter(UserGroup.is_active == True)\
                .first()
            
            if not group:
                return {
                    "success": False,
                    "error": "Group not found or already deleted"
                }
            
            # Soft delete the group
            group.is_active = False
            group.updated_at = datetime.utcnow()
            
            # Also deactivate all memberships
            memberships = db.query(UserGroupMembership)\
                .filter(UserGroupMembership.group_id == group_id)\
                .filter(UserGroupMembership.is_active == True)\
                .all()
            
            for membership in memberships:
                membership.is_active = False
            
            db.commit()
            
            # Log group deletion
            auth_logger.info(
                f"User group deleted: {group.name}",
                group_id=group_id,
                deleted_by=deleted_by,
                memberships_deactivated=len(memberships),
                event_type="group_deleted"
            )
            
            return {
                "success": True,
                "message": f"Group '{group.name}' deleted successfully",
                "memberships_deactivated": len(memberships)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error deleting user group: {str(e)}",
                group_id=group_id,
                error=str(e),
                event_type="group_deletion_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to delete group: {str(e)}"
            }
    
    @staticmethod
    def add_user_to_group(
        db: Session,
        group_id: int,
        user_id: int,
        added_by: int = None,
        expires_at: datetime = None
    ) -> Dict[str, Any]:
        """
        Add a user to a group
        
        Args:
            db: Database session
            group_id: ID of the group
            user_id: ID of the user to add
            added_by: ID of the user adding the member
            expires_at: When the membership expires (optional)
            
        Returns:
            Dictionary with addition result
        """
        try:
            # Check if group exists and is active
            group = db.query(UserGroup)\
                .filter(UserGroup.id == group_id)\
                .filter(UserGroup.is_active == True)\
                .first()
            
            if not group:
                return {
                    "success": False,
                    "error": "Group not found or inactive"
                }
            
            # Check if user is already in the group
            existing = db.query(UserGroupMembership)\
                .filter(UserGroupMembership.group_id == group_id)\
                .filter(UserGroupMembership.user_id == user_id)\
                .filter(UserGroupMembership.is_active == True)\
                .first()
            
            if existing:
                return {
                    "success": False,
                    "error": "User is already a member of this group"
                }
            
            # Create membership
            membership = UserGroupMembership(
                user_id=user_id,
                group_id=group_id,
                added_by=added_by,
                added_at=datetime.utcnow(),
                expires_at=expires_at,
                is_active=True
            )
            
            db.add(membership)
            db.commit()
            db.refresh(membership)
            
            # Log membership addition
            auth_logger.info(
                f"User added to group: {group.name}",
                user_id=user_id,
                group_id=group_id,
                added_by=added_by,
                event_type="user_added_to_group"
            )
            
            return {
                "success": True,
                "membership_id": membership.id,
                "message": f"User added to group '{group.name}' successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error adding user to group: {str(e)}",
                group_id=group_id,
                user_id=user_id,
                error=str(e),
                event_type="user_add_to_group_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to add user to group: {str(e)}"
            }
    
    @staticmethod
    def remove_user_from_group(
        db: Session,
        group_id: int,
        user_id: int,
        removed_by: int = None
    ) -> Dict[str, Any]:
        """
        Remove a user from a group
        
        Args:
            db: Database session
            group_id: ID of the group
            user_id: ID of the user to remove
            removed_by: ID of the user removing the member
            
        Returns:
            Dictionary with removal result
        """
        try:
            # Find the membership
            membership = db.query(UserGroupMembership)\
                .filter(UserGroupMembership.group_id == group_id)\
                .filter(UserGroupMembership.user_id == user_id)\
                .filter(UserGroupMembership.is_active == True)\
                .first()
            
            if not membership:
                return {
                    "success": False,
                    "error": "User is not a member of this group"
                }
            
            # Remove membership
            membership.is_active = False
            
            db.commit()
            
            # Get group name for logging
            group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
            group_name = group.name if group else f"Group {group_id}"
            
            # Log membership removal
            auth_logger.info(
                f"User removed from group: {group_name}",
                user_id=user_id,
                group_id=group_id,
                removed_by=removed_by,
                event_type="user_removed_from_group"
            )
            
            return {
                "success": True,
                "message": f"User removed from group '{group_name}' successfully"
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error removing user from group: {str(e)}",
                group_id=group_id,
                user_id=user_id,
                error=str(e),
                event_type="user_remove_from_group_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to remove user from group: {str(e)}"
            }
    
    @staticmethod
    def get_group_members(
        db: Session,
        group_id: int,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Get all members of a group
        
        Args:
            db: Database session
            group_id: ID of the group
            include_inactive: Include inactive memberships
            
        Returns:
            Dictionary with group members
        """
        try:
            query = db.query(UserGroupMembership, User)\
                .join(User, UserGroupMembership.user_id == User.id)\
                .filter(UserGroupMembership.group_id == group_id)
            
            if not include_inactive:
                query = query.filter(UserGroupMembership.is_active == True)
            
            memberships = query.all()
            
            members_data = []
            for membership, user in memberships:
                members_data.append({
                    "membership_id": membership.id,
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "added_at": membership.added_at.isoformat(),
                    "expires_at": membership.expires_at.isoformat() if membership.expires_at else None,
                    "is_active": membership.is_active
                })
            
            return {
                "success": True,
                "members": members_data,
                "total_count": len(members_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting group members: {str(e)}",
                group_id=group_id,
                error=str(e),
                event_type="group_members_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get group members: {str(e)}"
            }
    
    @staticmethod
    def get_user_groups(
        db: Session,
        user_id: int,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Get all groups a user belongs to
        
        Args:
            db: Database session
            user_id: ID of the user
            include_inactive: Include inactive memberships
            
        Returns:
            Dictionary with user groups
        """
        try:
            query = db.query(UserGroupMembership, UserGroup)\
                .join(UserGroup, UserGroupMembership.group_id == UserGroup.id)\
                .filter(UserGroupMembership.user_id == user_id)
            
            if not include_inactive:
                query = query.filter(UserGroupMembership.is_active == True)\
                    .filter(UserGroup.is_active == True)
            
            memberships = query.all()
            
            groups_data = []
            for membership, group in memberships:
                groups_data.append({
                    "membership_id": membership.id,
                    "group_id": group.id,
                    "group_name": group.name,
                    "group_description": group.description,
                    "organization_id": group.organization_id,
                    "added_at": membership.added_at.isoformat(),
                    "expires_at": membership.expires_at.isoformat() if membership.expires_at else None,
                    "is_active": membership.is_active
                })
            
            return {
                "success": True,
                "groups": groups_data,
                "total_count": len(groups_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting user groups: {str(e)}",
                user_id=user_id,
                error=str(e),
                event_type="user_groups_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get user groups: {str(e)}"
            }
    
    @staticmethod
    def get_organization_groups(
        db: Session,
        organization_id: int,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Get all groups in an organization
        
        Args:
            db: Database session
            organization_id: ID of the organization
            include_inactive: Include inactive groups
            
        Returns:
            Dictionary with organization groups
        """
        try:
            query = db.query(UserGroup)\
                .filter(UserGroup.organization_id == organization_id)
            
            if not include_inactive:
                query = query.filter(UserGroup.is_active == True)
            
            groups = query.order_by(UserGroup.created_at.desc()).all()
            
            groups_data = []
            for group in groups:
                # Get member count
                member_count = db.query(UserGroupMembership)\
                    .filter(UserGroupMembership.group_id == group.id)\
                    .filter(UserGroupMembership.is_active == True)\
                    .count()
                
                groups_data.append({
                    "id": group.id,
                    "name": group.name,
                    "description": group.description,
                    "organization_id": group.organization_id,
                    "created_by": group.created_by,
                    "created_at": group.created_at.isoformat(),
                    "updated_at": group.updated_at.isoformat(),
                    "is_active": group.is_active,
                    "member_count": member_count
                })
            
            return {
                "success": True,
                "groups": groups_data,
                "total_count": len(groups_data)
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting organization groups: {str(e)}",
                organization_id=organization_id,
                error=str(e),
                event_type="organization_groups_retrieval_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get organization groups: {str(e)}"
            }
    
    @staticmethod
    def get_group_statistics(
        db: Session,
        organization_id: int = None
    ) -> Dict[str, Any]:
        """
        Get group statistics
        
        Args:
            db: Database session
            organization_id: Filter by organization
            
        Returns:
            Dictionary with group statistics
        """
        try:
            query = db.query(UserGroup)
            
            if organization_id:
                query = query.filter(UserGroup.organization_id == organization_id)
            
            # Get total groups
            total_groups = query.count()
            
            # Get active groups
            active_groups = query.filter(UserGroup.is_active == True).count()
            
            # Get total memberships
            membership_query = db.query(UserGroupMembership)
            if organization_id:
                membership_query = membership_query.join(UserGroup, UserGroupMembership.group_id == UserGroup.id)\
                    .filter(UserGroup.organization_id == organization_id)
            
            total_memberships = membership_query.count()
            active_memberships = membership_query.filter(UserGroupMembership.is_active == True).count()
            
            return {
                "success": True,
                "statistics": {
                    "total_groups": total_groups,
                    "active_groups": active_groups,
                    "inactive_groups": total_groups - active_groups,
                    "total_memberships": total_memberships,
                    "active_memberships": active_memberships,
                    "inactive_memberships": total_memberships - active_memberships
                }
            }
            
        except Exception as e:
            auth_logger.error(
                f"Error getting group statistics: {str(e)}",
                organization_id=organization_id,
                error=str(e),
                event_type="group_statistics_error"
            )
            
            return {
                "success": False,
                "error": f"Failed to get group statistics: {str(e)}"
            }
