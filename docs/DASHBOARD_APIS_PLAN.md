# 📊 DASHBOARD APIS PLAN
**FastAPI User Management System**

---

## 🎯 GOAL
Create comprehensive dashboard APIs for different user roles with appropriate data visibility and management capabilities.

---

## 📋 DASHBOARD REQUIREMENTS BY ROLE

### **Role Hierarchy:**
```
👑 Super Admin
├── 🏢 Organization Admin
│   ├── 👨‍💼 Admin
│   │   └── 👤 User
│   └── 👤 User
└── 👤 User (Direct)
```

---

## 👑 SUPER ADMIN DASHBOARD

### **What Super Admin Needs to See:**

#### **1. System Overview**
```json
GET /api/v1/dashboard/super-admin/overview

Response:
{
  "total_organizations": 25,
  "total_users": 1500,
  "total_admins": 125,
  "total_sessions": 850,
  "active_sessions": 650,
  "total_api_keys": 50,
  "total_audit_logs_today": 5000,
  "system_health": {
    "database": "healthy",
    "redis": "healthy",
    "email": "healthy"
  }
}
```

#### **2. User Statistics**
```json
GET /api/v1/dashboard/super-admin/users/stats

Response:
{
  "total_users": 1500,
  "active_users": 1200,
  "locked_users": 10,
  "users_by_role": {
    "super_admin": 5,
    "organization_admin": 50,
    "admin": 125,
    "user": 1320
  },
  "users_today": 25,
  "users_this_week": 150,
  "users_this_month": 500
}
```

#### **3. Organization Statistics**
```json
GET /api/v1/dashboard/super-admin/organizations/stats

Response:
{
  "total_organizations": 25,
  "active_organizations": 20,
  "organizations_by_size": {
    "small": 10,      // < 10 users
    "medium": 10,     // 10-100 users
    "large": 5        // > 100 users
  },
  "total_users_per_org": {
    "org1": 150,
    "org2": 200,
    "org3": 100
  }
}
```

#### **4. Session Analytics**
```json
GET /api/v1/dashboard/super-admin/sessions/stats

Response:
{
  "total_sessions": 850,
  "active_sessions": 650,
  "sessions_by_device": {
    "desktop": 400,
    "mobile": 200,
    "tablet": 50
  },
  "sessions_by_browser": {
    "Chrome": 500,
    "Firefox": 150,
    "Safari": 100
  },
  "average_session_duration": "2.5 hours"
}
```

#### **5. Audit Logs Dashboard**
```json
GET /api/v1/dashboard/super-admin/audit-logs/stats

Response:
{
  "total_logs_today": 5000,
  "logs_by_type": {
    "login": 2000,
    "logout": 1500,
    "password_change": 500,
    "user_creation": 200,
    "user_update": 300
  },
  "logs_by_status": {
    "success": 4500,
    "failure": 500
  },
  "recent_activity": [
    { "user": "admin", "action": "created_user", "time": "..." },
    { "user": "user1", "action": "login", "time": "..." }
  ]
}
```

#### **6. Security Dashboard**
```json
GET /api/v1/dashboard/super-admin/security/stats

Response:
{
  "failed_login_attempts_today": 50,
  "locked_accounts": 10,
  "accounts_by_lockout_reason": {
    "too_many_attempts": 8,
    "suspicious_activity": 2
  },
  "2fa_enabled_users": 800,
  "2fa_disabled_users": 700,
  "recent_security_events": [...]
}
```

#### **7. All Organizations List**
```json
GET /api/v1/dashboard/super-admin/organizations

Response:
{
  "organizations": [
    {
      "id": 1,
      "name": "TechCorp",
      "user_count": 150,
      "admin_count": 10,
      "active_sessions": 85,
      "status": "active",
      "created_at": "..."
    }
  ],
  "pagination": {...}
}
```

#### **8. System Health Check**
```json
GET /api/v1/dashboard/super-admin/system/health

Response:
{
  "database": {
    "status": "healthy",
    "connection_pool": {
      "active": 15,
      "idle": 5,
      "total": 20
    },
    "slow_queries_today": 5
  },
  "redis": {
    "status": "healthy",
    "memory_usage": "500MB",
    "hit_rate": "85%"
  },
  "email": {
    "status": "healthy",
    "emails_sent_today": 250,
    "emails_failed_today": 2
  },
  "disk_usage": {
    "total": "100GB",
    "used": "45GB",
    "free": "55GB"
  }
}
```

---

## 🏢 ORGANIZATION ADMIN DASHBOARD

### **What Organization Admin Needs to See:**

#### **1. Organization Overview**
```json
GET /api/v1/dashboard/organization-admin/overview

Response:
{
  "organization": {
    "id": 1,
    "name": "TechCorp",
    "total_users": 150,
    "total_admins": 10,
    "active_sessions": 85,
    "total_api_keys": 15
  },
  "today_stats": {
    "logins": 50,
    "new_users": 2,
    "password_resets": 5,
    "audit_logs": 500
  }
}
```

#### **2. Organization Users Dashboard**
```json
GET /api/v1/dashboard/organization-admin/users/stats

Response:
{
  "total_users": 150,
  "active_users": 120,
  "locked_users": 2,
  "users_by_role": {
    "admin": 10,
    "user": 140
  },
  "new_users_today": 2,
  "new_users_this_week": 15,
  "recent_users": [...]
}
```

#### **3. Organization Activity**
```json
GET /api/v1/dashboard/organization-admin/activity/stats

Response:
{
  "total_activity_today": 500,
  "activity_by_type": {
    "login": 200,
    "logout": 150,
    "password_change": 50,
    "user_creation": 10
  },
  "top_users_by_activity": [...],
  "activity_timeline": [...]
}
```

#### **4. Organization Sessions**
```json
GET /api/v1/dashboard/organization-admin/sessions/stats

Response:
{
  "total_sessions": 150,
  "active_sessions": 85,
  "sessions_by_device": {...},
  "average_session_duration": "2 hours",
  "recent_sessions": [...]
}
```

---

## 👨‍💼 ADMIN DASHBOARD

### **What Admin Needs to See:**

#### **1. Admin Overview**
```json
GET /api/v1/dashboard/admin/overview

Response:
{
  "total_users": 150,
  "active_users": 120,
  "active_sessions": 85,
  "today_stats": {
    "logins": 50,
    "new_users": 2,
    "password_resets": 5
  }
}
```

#### **2. User Management Dashboard**
```json
GET /api/v1/dashboard/admin/users/stats

Response:
{
  "total_users": 150,
  "active_users": 120,
  "locked_users": 2,
  "users_by_status": {
    "active": 120,
    "inactive": 28,
    "locked": 2
  },
  "recent_users": [...]
}
```

#### **3. User Activity**
```json
GET /api/v1/dashboard/admin/activity/stats

Response:
{
  "total_activity_today": 500,
  "activity_by_type": {...},
  "recent_activity": [...]
}
```

---

## 👤 USER DASHBOARD

### **What User Needs to See:**

#### **1. Personal Overview**
```json
GET /api/v1/dashboard/user/overview

Response:
{
  "profile": {
    "username": "john_doe",
    "email": "john@example.com",
    "role": "user",
    "status": "active"
  },
  "active_sessions": 3,
  "last_login": "2024-01-15T10:30:00Z",
  "account_created": "2024-01-01T00:00:00Z"
}
```

#### **2. Account Activity**
```json
GET /api/v1/dashboard/user/activity

Response:
{
  "recent_activity": [
    { "action": "login", "time": "...", "ip": "..." },
    { "action": "password_change", "time": "..." },
    { "action": "profile_update", "time": "..." }
  ],
  "total_logins_today": 1,
  "total_logins_this_week": 5,
  "total_logins_this_month": 20
}
```

#### **3. Active Sessions**
```json
GET /api/v1/dashboard/user/sessions

Response:
{
  "active_sessions": [
    {
      "device": "Chrome on Windows",
      "location": "New York, USA",
      "last_active": "...",
      "ip_address": "..."
    }
  ],
  "can_revoke": true
}
```

---

## 🎨 DASHBOARD UI REQUIREMENTS

### **Common Elements:**
1. **Navigation Bar** - Role-based menu
2. **Statistics Cards** - Key metrics at a glance
3. **Data Tables** - Sortable, filterable, paginated
4. **Charts & Graphs** - Visual data representation
5. **Real-time Updates** - Live data refresh

### **Dashboard Layout:**

#### **Super Admin Dashboard:**
```
┌─────────────────────────────────────────────┐
│  System Overview (Cards)                     │
├─────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Orgs: 25 │  │ Users:1.5K│ │Sessions:850│ │
│  └──────────┘  └──────────┘  └──────────┘ │
├─────────────────────────────────────────────┤
│  Organizations Table (with actions)         │
├─────────────────────────────────────────────┤
│  System Health Status                       │
└─────────────────────────────────────────────┘
```

#### **Organization Admin Dashboard:**
```
┌─────────────────────────────────────────────┐
│  Organization: TechCorp                     │
├─────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Users:150│  │Admins:10 │ │Active:85  │ │
│  └──────────┘  └──────────┘  └──────────┘ │
├─────────────────────────────────────────────┤
│  User Management Table                      │
├─────────────────────────────────────────────┤
│  Activity Timeline (Chart)                  │
└─────────────────────────────────────────────┘
```

#### **Admin Dashboard:**
```
┌─────────────────────────────────────────────┐
│  User Management                            │
├─────────────────────────────────────────────┤
│  User Statistics Cards                      │
├─────────────────────────────────────────────┤
│  Users Table (with filters)                 │
├─────────────────────────────────────────────┤
│  Recent User Activity                      │
└─────────────────────────────────────────────┘
```

#### **User Dashboard:**
```
┌─────────────────────────────────────────────┐
│  My Profile                                 │
├─────────────────────────────────────────────┤
│  Account Information                        │
├─────────────────────────────────────────────┤
│  Active Sessions                            │
├─────────────────────────────────────────────┤
│  Recent Activity                            │
└─────────────────────────────────────────────┘
```

---

## 📝 IMPLEMENTATION PLAN

### **Phase 1: Endpoints** (Day 1-2)
- Create dashboard route files
- Implement role-based endpoints
- Add data aggregation logic
- Add caching for dashboard data

### **Phase 2: Authentication** (Day 3)
- Add role-based access control
- Verify user permissions
- Add rate limiting

### **Phase 3: Testing** (Day 4)
- Write integration tests
- Test with different roles
- Verify data accuracy

---

## 🚀 RECOMMENDED IMPLEMENTATION ORDER

### **Phase 1: User Dashboard** (Start Here) ⭐
**Why First:**
- Simplest scope (personal data only)
- No complex aggregations
- Establishes baseline patterns
- Quick to implement and test

**Endpoints:**
1. `/api/v1/dashboard/user/overview` - Personal overview
2. `/api/v1/dashboard/user/activity` - Account activity
3. `/api/v1/dashboard/user/sessions` - Active sessions

**Estimated Time:** 1-2 hours

---

### **Phase 2: Admin Dashboard**
**Why Second:**
- Builds on User Dashboard patterns
- Adds user management features
- Includes organization-level statistics

**Endpoints:**
1. `/api/v1/dashboard/admin/overview`
2. `/api/v1/dashboard/admin/users/stats`
3. `/api/v1/dashboard/admin/activity/stats`

**Estimated Time:** 2-3 hours

---

### **Phase 3: Organization Admin Dashboard**
**Why Third:**
- More complex than Admin
- Adds organization management
- Multi-level data aggregation

**Endpoints:**
1. `/api/v1/dashboard/organization-admin/overview`
2. `/api/v1/dashboard/organization-admin/users/stats`
3. `/api/v1/dashboard/organization-admin/activity/stats`
4. `/api/v1/dashboard/organization-admin/sessions/stats`

**Estimated Time:** 3-4 hours

---

### **Phase 4: Super Admin Dashboard**
**Why Last:**
- Most complex (system-wide view)
- Requires all previous patterns
- Needs most data aggregation

**Endpoints:**
1. `/api/v1/dashboard/super-admin/overview`
2. `/api/v1/dashboard/super-admin/users/stats`
3. `/api/v1/dashboard/super-admin/organizations/stats`
4. `/api/v1/dashboard/super-admin/sessions/stats`
5. `/api/v1/dashboard/super-admin/audit-logs/stats`
6. `/api/v1/dashboard/super-admin/security/stats`
7. `/api/v1/dashboard/super-admin/organizations` (list)
8. `/api/v1/dashboard/super-admin/system/health`

**Estimated Time:** 4-5 hours

---

## 📊 TOTAL ESTIMATED TIME

| Phase | Time | Complexity |
|-------|------|------------|
| Phase 1: User | 1-2h | Easy |
| Phase 2: Admin | 2-3h | Medium |
| Phase 3: Org Admin | 3-4h | Medium-Hard |
| Phase 4: Super Admin | 4-5h | Hard |
| **TOTAL** | **10-14h** | **Progressive** |

---

## ✅ RECOMMENDATION

**Start with:** User Dashboard  
**Reason:** Establishes patterns, quick win, validates approach  
**Next:** Admin → Organization Admin → Super Admin

**Ready to implement User Dashboard?**

