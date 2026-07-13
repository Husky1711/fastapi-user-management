"""Dashboard APIs — thin HTTP layer over services/dashboard."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies.auth import AdminUser, CurrentUser, DashboardSuperAdminUser, OrgAdminUser
from schemas.dashboard import (
    AdminActivityStats,
    AdminDashboardOverview,
    AdminUsersStats,
    UserActivityResponse,
    UserDashboardOverview,
    UserSessionsResponse,
)
from services.dashboard import (
    AdminDashboardService,
    OrgAdminDashboardService,
    SuperAdminDashboardService,
    UserDashboardService,
)
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/user/overview", response_model=UserDashboardOverview)
async def get_user_dashboard_overview(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return UserDashboardService.get_user_dashboard_overview(current_user, db)


@router.get("/user/activity", response_model=UserActivityResponse)
async def get_user_activity(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return UserDashboardService.get_user_activity(current_user, db)


@router.get("/user/sessions", response_model=UserSessionsResponse)
async def get_user_sessions_dashboard(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return UserDashboardService.get_user_sessions_dashboard(current_user, db)


@router.get("/admin/overview", response_model=AdminDashboardOverview)
async def get_admin_dashboard_overview(
    current_user: AdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return AdminDashboardService.get_admin_dashboard_overview(current_user, db)


@router.get("/admin/users/stats", response_model=AdminUsersStats)
async def get_admin_users_stats(
    current_user: AdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return AdminDashboardService.get_admin_users_stats(current_user, db)


@router.get("/admin/activity/stats", response_model=AdminActivityStats)
async def get_admin_activity_stats(
    current_user: AdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return AdminDashboardService.get_admin_activity_stats(current_user, db)


@router.get("/organization-admin/overview")
async def get_organization_admin_overview(
    current_user: OrgAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return OrgAdminDashboardService.get_organization_admin_overview(current_user, db)


@router.get("/organization-admin/users/stats")
async def get_organization_admin_users_stats(
    current_user: OrgAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return OrgAdminDashboardService.get_organization_admin_users_stats(
        current_user, db
    )


@router.get("/organization-admin/sessions/stats")
async def get_organization_admin_sessions_stats(
    current_user: OrgAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return OrgAdminDashboardService.get_organization_admin_sessions_stats(
        current_user, db
    )


@router.get("/super-admin/overview")
async def get_super_admin_overview(
    current_user: DashboardSuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return SuperAdminDashboardService.get_super_admin_overview(current_user, db)


@router.get("/super-admin/users/stats")
async def get_super_admin_users_stats(
    current_user: DashboardSuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return SuperAdminDashboardService.get_super_admin_users_stats(current_user, db)


@router.get("/super-admin/organizations/stats")
async def get_super_admin_organizations_stats(
    current_user: DashboardSuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return SuperAdminDashboardService.get_super_admin_organizations_stats(
        current_user, db
    )


@router.get("/super-admin/sessions/stats")
async def get_super_admin_sessions_stats(
    current_user: DashboardSuperAdminUser,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("dashboard")),
):
    return SuperAdminDashboardService.get_super_admin_sessions_stats(current_user, db)
