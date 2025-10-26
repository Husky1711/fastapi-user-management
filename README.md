# 🚀 FastAPI User Management System

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.119+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black.svg)](https://black.readthedocs.io)

A production-ready, enterprise-grade user management system built with FastAPI, featuring JWT authentication, Two-Factor Authentication (2FA), automated backups, email service integration, Redis-based rate limiting, multi-tenant architecture, and comprehensive logging.

## ✨ Features

### 🔐 **Authentication & Authorization**
- **JWT-based authentication** with access & refresh tokens
- **Two-Factor Authentication (2FA)** with TOTP support (Google Authenticator)
- **QR code generation** for easy 2FA setup
- **Backup codes** for account recovery
- **Account lockout protection** after 5 failed attempts
- **Login attempt tracking** with IP and device fingerprinting
- **Role-based access control (RBAC)** with hierarchical permissions
- **Multi-tenant architecture** supporting organizations and users
- **Secure password hashing** with SHA-256
- **Advanced session management** with 5 different strategies
- **Auto-refresh token service** for seamless user experience
- **Enhanced login service** with session control options
- **Token rotation** and session cleanup

### 🛡️ **Security & Rate Limiting**
- **Redis-based rate limiting** with sliding window algorithm
- **Per-endpoint rate limits** (minute, hour, day windows)
- **IP-based global rate limiting**
- **Fail-open/fail-closed** configuration for Redis outages
- **Account lockout protection** after failed login attempts

### 📊 **Monitoring & Logging**
- **Structured JSON logging** with correlation IDs
- **Specialized loggers** (API, Auth, Database, Security)
- **Log rotation** with configurable retention
- **Performance monitoring** with request duration tracking
- **Production-ready logging** with context variables

### ⚙️ **Configuration Management**
- **Centralized configuration** using Pydantic Settings
- **Environment-specific settings** (dev, staging, production)
- **Type-safe configuration** with validation
- **Easy environment switching** with helper scripts

### 🗄️ **Database Integration**
- **MySQL database** with SQLAlchemy ORM
- **Connection pooling** with configurable settings
- **Database migrations** support
- **User and session management** models
- **Complete schema dump** available (`database_schema.sql`)

### 🏢 **Production Features**
- **Email Service** - SMTP integration with welcome emails, password resets, and security alerts
- **Automated Backups** - Daily MySQL backups with 30-day retention and restoration scripts
- **Password History Tracking** - Prevent password reuse with configurable history limits
- **Comprehensive Audit Logging** - Complete audit trail for compliance (SOX, GDPR, HIPAA)
- **Advanced Session Management** - Device fingerprinting, session statistics, cleanup
- **Granular Permissions** - Resource-specific permissions with time limits
- **User Groups Management** - Organization-based group management
- **API Key Management** - Secure API key generation and validation
- **Production API Endpoints** - Enterprise-grade endpoints for all features

## 🏗️ **Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │────│   MySQL DB      │    │   Redis Cache   │
│                 │    │                 │    │                 │
│ • JWT Auth      │    │ • Users         │    │ • Rate Limiting │
│ • Rate Limiting │    │ • Sessions      │    │ • Session Store │
│ • Logging       │    │ • Organizations │    │ • Caching       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔄 **User Access Control Flow Diagram**

### **Role Hierarchy & Permissions**

```
👑 Super Admin
├── 🏢 Organization Admin
│   ├── 👨‍💼 Admin
│   │   └── 👤 User
│   └── 👤 User
└── 👤 User (Direct)
```

#### **Simplified Organizational Structure**
```mermaid
graph TD
    SA[👑 Super Admin<br/>System Administrator] --> OA1[🏢 Organization/Client Admin 1<br/>Organization Manager]
    SA --> OA2[🏢 Organization/Client Admin 2<br/>Organization Manager]
    
    OA1 --> A1[👨‍💼 Admin 1<br/>Department Admin]
    OA1 --> U1[👤 User 1<br/>Organization User]
    
    OA2 --> U2[👤 User 2<br/>Organization User]
    
    A1 --> U3[👤 User 3<br/>Department User]
    
    SA -.->|Direct Access| U4[👤 Direct User<br/>System User]
    
    classDef superAdmin fill:#e74c3c,stroke:#c0392b,stroke-width:4px,color:#fff
    classDef orgAdmin fill:#3498db,stroke:#2980b9,stroke-width:3px,color:#fff
    classDef admin fill:#9b59b6,stroke:#8e44ad,stroke-width:2px,color:#fff
    classDef user fill:#27ae60,stroke:#229954,stroke-width:2px,color:#fff
    
    class SA superAdmin
    class OA1,OA2 orgAdmin
    class A1 admin
    class U1,U2,U3,U4 user
```

#### **Access Control Matrix**
```mermaid
graph LR
    subgraph "👑 Super Admin Access"
        SA1[All Organizations]
        SA2[All Users]
        SA3[All Sessions]
        SA4[System Settings]
    end
    
    subgraph "🏢 Organization Admin Access"
        OA1[Own Organization]
        OA2[Org Admins & Users]
        OA3[Org Sessions]
        OA4[Org Settings]
    end
    
    subgraph "👨‍💼 Admin Access"
        A1[Own Organization]
        A2[Org Users Only]
        A3[User Sessions]
        A4[User Management]
    end
    
    subgraph "👤 User Access"
        U1[Own Profile]
        U2[Own Sessions]
        U3[Basic Operations]
        U4[Limited Access]
    end
    
    SA1 --> OA1
    SA2 --> OA2
    SA3 --> OA3
    SA4 --> OA4
    
    OA1 --> A1
    OA2 --> A2
    OA3 --> A3
    OA4 --> A4
    
    A1 --> U1
    A2 --> U2
    A3 --> U3
    A4 --> U4
```

### **What Each Role Can See**

| Role | `/users` Endpoint | `/users/{id}` Endpoint | `/sessions` Endpoint | Organization Access |
|------|------------------|------------------------|---------------------|-------------------|
| **👑 Super Admin** | ✅ All users grouped by organization | ✅ Any user from any organization | ✅ All sessions | ✅ All organizations |
| **🏢 Organization Admin** | ✅ Admins & users in own organization | ✅ Users in own organization | ✅ Sessions in own organization | ✅ Own organization only |
| **👨‍💼 Admin** | ✅ Users in own organization | ✅ Users in own organization | ✅ Sessions in own organization | ✅ Own organization only |
| **👤 User** | ✅ Own profile only | ✅ Own profile only | ✅ Own sessions only | ❌ No organization access |

### **Data Visibility Flow**

```
User Login → Authentication → Role Check → Data Access

👑 Super Admin:
├── 📊 All Organizations Data
├── 👥 All Users Data  
├── 🔐 All Sessions Data
└── ⚙️ System Management

🏢 Organization Admin:
├── 📊 Own Organization Data
├── 👥 Admins & Users in Org
├── 🔐 Sessions in Org
└── ⚙️ Organization Management

👨‍💼 Admin:
├── 📊 Own Organization Data
├── 👥 Users in Org
├── 🔐 User Sessions in Org
└── ⚙️ User Management

👤 User:
├── 📊 Own Profile Data
├── 👥 Own Profile Only
├── 🔐 Own Sessions Only
└── ⚙️ Basic Operations
```

### **Multi-Tenant Organization Structure**

```
🏢 System
├── 🏢 Organization 1 (TechCorp)
│   ├── 👨‍💼 Admin 1
│   ├── 👤 User 1
│   └── 👤 User 2
├── 🏢 Organization 2 (FinanceInc)
│   ├── 👨‍💼 Admin 2
│   ├── 👤 User 1
│   └── 👤 User 2
├── 🏢 Organization 3 (HealthOrg)
│   ├── 👨‍💼 Admin 3
│   └── 👤 User 1
└── 🏢 Organization 4 (EduCorp)
    ├── 👨‍💼 Admin 4
    ├── 👤 User 1
    └── 👤 User 2

👑 Super Admin can access ALL organizations
```

### **Session Management Strategies**

```
User Login → Session Strategy → Action

✅ allow_multiple:     Allow unlimited sessions
🔄 replace_all:        Replace all existing sessions  
🔄 replace_same_device: Replace sessions from same device
❌ deny_if_exists:     Deny login if sessions exist
📊 limit_sessions:     Limit to max sessions (default: 5)
```

### **API Response Examples**

#### **Super Admin Response (`/users`)**
```json
{
  "1": {
    "organization_id": 1,
    "users": [
      {"id": 1, "username": "admin1", "role": "admin", "organization_id": 1},
      {"id": 2, "username": "user1", "role": "user", "organization_id": 1}
    ]
  },
  "2": {
    "organization_id": 2,
    "users": [
      {"id": 3, "username": "admin2", "role": "admin", "organization_id": 2},
      {"id": 4, "username": "user2", "role": "user", "organization_id": 2}
    ]
  }
}
```

#### **Organization Admin Response (`/users`)**
```json
{
  "organization_id": 1,
  "users": [
    {"id": 1, "username": "admin1", "role": "admin", "organization_id": 1},
    {"id": 2, "username": "user1", "role": "user", "organization_id": 1}
  ]
}
```

#### **Regular User Response (`/users`)**
```json
{
  "id": 2,
  "username": "user1",
  "email": "user1@example.com",
  "role": "user",
  "organization_id": 1,
  "status": "active"
}
```

### **Visual Flow Diagrams**

#### **Role-Based Access Control Flow**
```mermaid
graph TD
    A[👑 Super Admin] --> B[🏢 Organization Admin]
    B --> C[👨‍💼 Admin]
    C --> D[👤 User]
    
    A --> A1[📊 All Organizations]
    A --> A2[👥 All Users]
    A --> A3[🔐 All Sessions]
    A --> A4[⚙️ System Management]
    
    B --> B1[📊 Own Organization]
    B --> B2[👥 Admins & Users in Org]
    B --> B3[🔐 Sessions in Org]
    B --> B4[⚙️ Organization Management]
    
    C --> C1[📊 Own Organization]
    C --> C2[👥 Users in Org]
    C --> C3[🔐 User Sessions in Org]
    C --> C4[⚙️ User Management]
    
    D --> D1[📊 Own Profile]
    D --> D2[👥 Own Profile Only]
    D --> D3[🔐 Own Sessions Only]
    D --> D4[⚙️ Basic Operations]
```

#### **Multi-Tenant Organization Structure**
```mermaid
graph TD
    System[🏢 System] --> Org1[🏢 Organization 1<br/>TechCorp]
    System --> Org2[🏢 Organization 2<br/>FinanceInc]
    System --> Org3[🏢 Organization 3<br/>HealthOrg]
    System --> Org4[🏢 Organization 4<br/>EduCorp]
    
    Org1 --> Org1Admin[👨‍💼 Admin 1]
    Org1 --> Org1User1[👤 User 1]
    Org1 --> Org1User2[👤 User 2]
    
    Org2 --> Org2Admin[👨‍💼 Admin 2]
    Org2 --> Org2User1[👤 User 1]
    Org2 --> Org2User2[👤 User 2]
    
    Org3 --> Org3Admin[👨‍💼 Admin 3]
    Org3 --> Org3User1[👤 User 1]
    
    Org4 --> Org4Admin[👨‍💼 Admin 4]
    Org4 --> Org4User1[👤 User 1]
    Org4 --> Org4User2[👤 User 2]
    
    SuperAdmin[👑 Super Admin] -.->|Can Access| Org1
    SuperAdmin -.->|Can Access| Org2
    SuperAdmin -.->|Can Access| Org3
    SuperAdmin -.->|Can Access| Org4
```

#### **Session Management Flow**
```mermaid
graph LR
    Login[User Login] --> Strategy{Session Strategy}
    
    Strategy -->|allow_multiple| AM[✅ Allow Multiple Sessions]
    Strategy -->|replace_all| RA[🔄 Replace All Sessions]
    Strategy -->|replace_same_device| RSD[🔄 Replace Same Device]
    Strategy -->|deny_if_exists| DIE[❌ Deny If Sessions Exist]
    Strategy -->|limit_sessions| LS[📊 Limit to Max Sessions]
    
    AM --> AM1[Unlimited Sessions]
    RA --> RA1[Revoke All Existing]
    RSD --> RSD1[Revoke Same Device Only]
    DIE --> DIE1[Block New Login]
    LS --> LS1[Enforce Session Limit]
```

### **Practical Examples**

#### **Scenario 1: Super Admin Login**
```bash
# Super Admin logs in
POST /api/v1/login
{
  "username": "superadmin",
  "password": "admin123"
}

# Gets access to ALL organizations
GET /api/v1/users
# Response: All users grouped by organization (Org 1, Org 2, Org 3, etc.)
```

#### **Scenario 2: Organization Admin Login**
```bash
# Organization Admin logs in
POST /api/v1/login
{
  "username": "orgadmin_techcorp",
  "password": "admin123"
}

# Gets access to ONLY TechCorp organization
GET /api/v1/users
# Response: Only TechCorp users (admins + users)
```

#### **Scenario 3: Regular Admin Login**
```bash
# Admin logs in
POST /api/v1/login
{
  "username": "admin_techcorp",
  "password": "admin123"
}

# Gets access to TechCorp users only
GET /api/v1/users
# Response: Only TechCorp users (no other admins)
```

#### **Scenario 4: Regular User Login**
```bash
# User logs in
POST /api/v1/login
{
  "username": "user_techcorp",
  "password": "user123"
}

# Gets access to own profile only
GET /api/v1/users
# Response: Only their own profile data
```

### **Session Management Examples**

#### **Allow Multiple Sessions**
```bash
# User can login from multiple devices
POST /api/v1/login-with-session-control?session_strategy=allow_multiple
# Result: All previous sessions remain active
```

#### **Replace All Sessions**
```bash
# User login replaces all existing sessions
POST /api/v1/login-with-session-control?session_strategy=replace_all
# Result: All previous sessions are revoked
```

#### **Deny If Sessions Exist**
```bash
# User tries to login when already logged in
POST /api/v1/login-with-session-control?session_strategy=deny_if_exists
# Result: Login denied with 400 Bad Request
```

## 🧪 **Testing**

### **Test Suite**
The project includes comprehensive test suites for all production features:

- **`simple_production_test.py`** - Quick verification of core production features
- **`comprehensive_test_suite.py`** - Full test suite for all production features

### **Test Results**
```
============================================================
SIMPLE PRODUCTION FEATURES TEST
============================================================

1. Testing Authentication...
   [PASS] Authentication successful

2. Testing 6 Core Endpoints...
   [PASS] Audit Logs: 24 records
   [PASS] Sessions: 13 records
   [PASS] Permissions: 0 records
   [PASS] Groups: 0 records
   [PASS] API Keys: 0 records
   [PASS] Password History: 3 records

3. Testing Password Change...
   [PASS] Password change successful

============================================================
TEST SUMMARY
============================================================
Tests Passed: 7/7 (100.0%)
*** EXCELLENT: Core production features are working! ***
```

### **Running Tests**
```bash
# Run simple production test
python simple_production_test.py

# Run comprehensive test suite
python comprehensive_test_suite.py
```

### **API Documentation**
- **Interactive Docs**: Visit `/docs` for Swagger UI
- **Alternative Docs**: Visit `/redoc` for ReDoc interface
- **Complete API Reference**: See `API_REFERENCE.md` for comprehensive endpoint documentation

---

## 🚀 **Quick Start**

### Prerequisites
- Python 3.10+
- MySQL 8.0+
- Redis 6.0+

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Husky1711/fastapi-user-management.git
   cd fastapi-user-management
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit configuration
   nano .env
   ```

5. **Set up database**
   ```bash
   # Create MySQL database
   mysql -u root -p
   CREATE DATABASE fastapi_users;
   ```

6. **Run the application**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 9000
   ```

---

## 🗄️ **Database Schema**

### **Schema Overview**
The system uses MySQL 8.0+ with a comprehensive schema designed for production use. A complete schema dump is available for easy database setup and migration.

### **Available Schema Files**
- **`database_schema.sql`** - Complete MySQL schema dump (created with `mysqldump`)
  - Contains all table structures, indexes, and constraints
  - No data included (schema-only dump)
  - Ready for production deployment

### **Core Tables**
| Table | Purpose | Key Features |
|-------|---------|--------------|
| `users` | Core user data | Role-based access, organization isolation |
| `organizations` | Multi-tenant organizations | Client/company management |
| `refresh_tokens` | JWT refresh token storage | Secure token management |
| `user_sessions` | Advanced session tracking | Device fingerprinting, statistics |
| `audit_logs` | Comprehensive audit trail | Compliance logging (SOX, GDPR, HIPAA) |
| `password_history` | Password change tracking | Prevent password reuse |
| `user_permissions` | Granular permissions | Resource-specific access control |
| `user_groups` | User group management | Organization-based groups |
| `user_group_memberships` | Group membership tracking | Many-to-many relationships |
| `api_keys` | API key management | Secure programmatic access |

### **Database Setup**
```bash
# Create database
mysql -u root -p
CREATE DATABASE fastapi_users;

# Import schema
mysql -u root -p fastapi_users < database_schema.sql

# Verify tables
mysql -u root -p fastapi_users
SHOW TABLES;
```

### **Schema Features**
- **No Foreign Key Constraints** - Uses indexes for performance
- **Comprehensive Indexing** - Optimized for production queries
- **Multi-tenant Ready** - Organization-based data isolation
- **Audit Trail** - Complete logging for compliance
- **Session Management** - Advanced session tracking
- **Security Focused** - Password history, API keys, permissions

---

## 📋 **Production API Endpoints**

### **Audit & Compliance**
- `GET /api/v1/audit/logs` - Get audit logs with filtering and pagination
- `GET /api/v1/audit/statistics` - Get audit statistics and analytics

### **Session Management**
- `GET /api/v1/sessions` - Get user sessions with device information
- `GET /api/v1/sessions/statistics` - Get session statistics
- `POST /api/v1/sessions/cleanup` - Clean up expired sessions

### **Permissions Management**
- `GET /api/v1/permissions` - Get user permissions
- `GET /api/v1/permissions/standard` - Get standard permissions list
- `GET /api/v1/permissions/statistics` - Get permission statistics

### **Groups Management**
- `GET /api/v1/groups` - Get organization groups
- `GET /api/v1/groups/{id}/members` - Get group members
- `GET /api/v1/groups/statistics` - Get group statistics

### **API Keys Management**
- `GET /api/v1/api-keys` - Get user API keys
- `GET /api/v1/api-keys/standard-permissions` - Get standard API permissions
- `GET /api/v1/api-keys/statistics` - Get API key statistics

### **Password History**
- `GET /api/v1/password/history` - Get password history
- `GET /api/v1/password/policy-stats` - Get password policy statistics

---

## 📋 **Core API Endpoints**

### Authentication
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/v1/login` | User login (with 2FA support) | 10/min, 100/hour |
| `POST` | `/api/v1/login-with-session-control` | Enhanced login with session management | 10/min, 100/hour |
| `POST` | `/api/v1/signup` | User registration | 5/min, 50/hour |
| `POST` | `/api/v1/refresh` | Refresh access token | 20/min, 200/hour |
| `POST` | `/api/v1/logout` | User logout | 10/min, 100/hour |
| `POST` | `/api/v1/logout-all` | Logout from all sessions | 5/min, 50/hour |

### Two-Factor Authentication (2FA)
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/v1/2fa/enable` | Enable 2FA for user | 5/min, 50/hour |
| `POST` | `/api/v1/2fa/verify` | Verify 2FA code | 20/min, 200/hour |
| `POST` | `/api/v1/2fa/disable` | Disable 2FA | 5/min, 50/hour |
| `GET` | `/api/v1/2fa/status` | Get 2FA status | 20/min, 200/hour |

### User Management
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/users` | Get all users (Role-based) | 5/min, 50/hour |
| `GET` | `/api/v1/users/{id}` | Get user by ID | 20/min, 200/hour |
| `POST` | `/api/v1/admin/users/create` | Create new user (Admin only) | 5/min, 50/hour |
| `GET` | `/api/v1/sessions` | Get user sessions | 10/min, 100/hour |
| `GET` | `/api/v1/sessions/info` | Get detailed session information | 10/min, 100/hour |
| `POST` | `/api/v1/sessions/revoke-others` | Revoke all other sessions | 5/min, 50/hour |
| `DELETE` | `/api/v1/sessions/{id}` | Revoke specific session | 5/min, 50/hour |

### System & Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Root endpoint with API info |
| `GET` | `/health` | Basic health check |
| `GET` | `/api/v1/health` | Versioned API health check |
| `GET` | `/health/detailed` | Detailed health with services |
| `GET` | `/health/ready` | Kubernetes readiness probe |
| `GET` | `/health/live` | Kubernetes liveness probe |
| `GET` | `/docs` | API documentation (Swagger UI) |
| `GET` | `/redoc` | Alternative API documentation |

## 🔄 **Enhanced Session Management**

### **Session Management Strategies**

The system supports 5 different session management strategies that can be configured per login:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `allow_multiple` | Allow unlimited sessions | Personal devices, trusted environments |
| `replace_all` | Replace all existing sessions (default) | Security-focused, single-device usage |
| `replace_same_device` | Replace sessions from same device | Device-specific security |
| `deny_if_exists` | Deny login if sessions exist | Maximum security, one session only |
| `limit_sessions` | Limit to max sessions per user | Balanced approach with configurable limits |

### **Auto-Refresh Token Service**

The system includes an intelligent auto-refresh service that:

- **Automatically refreshes** access tokens before expiration
- **Seamless user experience** without login interruptions
- **Background token management** with configurable intervals
- **Client-side integration** with JavaScript examples
- **Server-side middleware** for automatic token handling

### **Session Management Endpoints**

```bash
# Enhanced login with session control
POST /api/v1/login-with-session-control?session_strategy=replace_all
{
  "username": "user",
  "password": "password"
}

# Get detailed session information
GET /api/v1/sessions/info
Authorization: Bearer <token>

# Revoke all other sessions (keep current)
POST /api/v1/sessions/revoke-others
Authorization: Bearer <token>

# Logout from all sessions
POST /api/v1/logout-all
{
  "refresh_token": "your_refresh_token"
}
```

## 👥 **Admin User Creation API**

### **Overview**

The Admin User Creation API allows authorized administrators to create new users in the system with proper role-based permissions and organization isolation.

### **Who Can Use This API**

| Role | Permissions | Organization Scope |
|------|-------------|-------------------|
| **Super Admin** | Can create: Organization Admin, Admin, User | Any organization |
| **Organization Admin** | Can create: Admin, User | Own organization only |
| **Admin** | Can create: User only | Own organization only |
| **User** | Cannot create users | N/A (403 Forbidden) |

### **Role Hierarchy**

```
Super Admin
├── Organization Admin
│   ├── Admin
│   │   └── User
│   └── User
└── Admin
    └── User
```

### **API Endpoint**

```bash
POST /api/v1/admin/users/create
```

**Headers:**
```bash
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

### **Request Schema**

```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "optional_if_auto_generate",
  "role": "user",
  "organization_id": "optional_inherited_from_creator",
  "phone_number": "1234567890",
  "send_welcome_email": true,
  "auto_generate_password": true
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Username (3-50 chars, alphanumeric) |
| `email` | string | Yes | Valid email address |
| `password` | string | No* | Password (required if `auto_generate_password` is false) |
| `role` | string | No | User role (default: "user") |
| `organization_id` | integer | No | Organization ID (inherited from creator if not specified) |
| `phone_number` | string | No | Phone number (digits only) |
| `send_welcome_email` | boolean | No | Send welcome email (default: true) |
| `auto_generate_password` | boolean | No | Auto-generate secure password (default: true) |

### **Success Response**

```json
{
  "success": true,
  "message": "User 'newuser' created successfully",
  "user": {
    "id": 35,
    "username": "newuser",
    "email": "newuser@example.com",
    "role": "user",
    "organization_id": 1,
    "status": "active",
    "phone_number": "1234567890",
    "created_at": "2025-10-22T23:30:00",
    "last_login": null
  },
  "generated_password": "Kx9#mP2$vL8",
  "email_sent": false,
  "timestamp": "2025-10-22T23:30:00",
  "correlation_id": "abc123-def456"
}
```

### **Error Responses**

#### **401 Unauthorized**
```json
{
  "detail": "Could not validate credentials",
  "status_code": 401
}
```

#### **403 Forbidden**
```json
{
  "detail": "Users cannot create other users. Admin privileges required.",
  "status_code": 403
}
```

#### **400 Bad Request - Duplicate Username**
```json
{
  "detail": "Username 'newuser' already exists",
  "status_code": 400
}
```

#### **400 Bad Request - Role Permission**
```json
{
  "detail": "Role 'admin' cannot create users with role 'super_admin'",
  "status_code": 400
}
```

### **Usage Examples**

#### **Create User with Auto-Generated Password**
```bash
curl -X POST "http://localhost:9000/api/v1/admin/users/create" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "role": "user",
    "auto_generate_password": true,
    "send_welcome_email": false
  }'
```

#### **Create User with Custom Password**
```bash
curl -X POST "http://localhost:9000/api/v1/admin/users/create" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "customuser",
    "email": "customuser@example.com",
    "password": "CustomPass123",
    "role": "user",
    "auto_generate_password": false,
    "phone_number": "1234567890"
  }'
```

#### **Create Admin User (Super Admin only)**
```bash
curl -X POST "http://localhost:9000/api/v1/admin/users/create" \
  -H "Authorization: Bearer <super_admin_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newadmin",
    "email": "newadmin@example.com",
    "role": "admin",
    "organization_id": 1,
    "auto_generate_password": true
  }'
```

### **Security Features**

- **JWT Authentication**: Valid JWT token required
- **Role-based Authorization**: Only admins can create users
- **Organization Isolation**: Users can only create within their organization
- **Password Security**: Auto-generated passwords with complexity requirements
- **Input Validation**: Comprehensive validation for all fields
- **Duplicate Prevention**: Username and email uniqueness checks
- **Audit Logging**: All user creation events are logged
- **Rate Limiting**: 5 requests per minute, 50 per hour

### **Password Generation**

When `auto_generate_password` is true, the system generates a secure password with:
- **Length**: 12 characters (configurable)
- **Character Sets**: Lowercase, uppercase, digits, special characters
- **Requirements**: At least one character from each set
- **Security**: Cryptographically secure random generation

## 🔄 **API Versioning**

This API uses semantic versioning with the `/api/v1/` prefix for all endpoints. This ensures backward compatibility and allows for future API evolution.

### Version Strategy
- **Current Version**: `v1` (all endpoints under `/api/v1/`)
- **Future Versions**: `v2`, `v3`, etc. will be added as needed
- **Backward Compatibility**: Old versions will be maintained for a reasonable period
- **Deprecation Policy**: 6-month notice before removing old versions

### Versioned Endpoints
All API endpoints are prefixed with `/api/v1/`:
- Authentication: `/api/v1/login`, `/api/v1/signup`, `/api/v1/refresh`, `/api/v1/logout`
- User Management: `/api/v1/users`, `/api/v1/users/{id}`, `/api/v1/admin/users/create`, `/api/v1/sessions`
- Health Checks: `/api/v1/health`

### Non-Versioned Endpoints
System-level endpoints remain unversioned:
- Root: `/`
- Health: `/health`, `/health/detailed`, `/health/ready`, `/health/live`
- Documentation: `/docs`, `/redoc`

## ⚙️ **Configuration**

### Environment Variables

```bash
# Database Configuration
DB__URL="mysql+pymysql://user:password@localhost:3306/fastapi_users"
DB__ECHO=false
DB__POOL_SIZE=10

# Redis Configuration  
REDIS__HOST=localhost
REDIS__PORT=6379
REDIS__DB=0

# JWT Configuration
JWT__SECRET_KEY="your-super-secret-key-change-this-in-production"
JWT__ACCESS_TOKEN_EXPIRE_MINUTES=5
JWT__REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT__FAIL_OPEN=true
RATE_LIMIT__ENDPOINT_LIMITS__LOGIN__MINUTE=10

# Logging
LOG__LEVEL=INFO
LOG__LOG_DIR=logs
LOG__ENABLE_JSON=true
```

### Environment Management

```bash
# Switch environments
python config_manager.py development
python config_manager.py staging  
python config_manager.py production

# Show current config
python config_manager.py show

# List available environments
python config_manager.py list
```

## 🏢 **Multi-Tenant Architecture**

### Role Hierarchy
```
Super Admin
    ├── Organization/Client Admin
    │   ├── Admin
    │   │   └── User
    │   └── User
    └── Organization/Client Admin
        └── User
```

### Access Control
- **Super Admin**: Full system access
- **Organization Admin**: Manage users within their organization
- **Admin**: Manage users within their scope
- **User**: Basic user access

## 📊 **Rate Limiting**

### Global Limits
- **Per IP**: 1000 requests/minute, 10,000/hour, 100,000/day

### Endpoint-Specific Limits
- **Login**: 10/minute, 100/hour
- **Signup**: 5/minute, 50/hour
- **Users List**: 5/minute, 50/hour
- **User Detail**: 20/minute, 200/hour

### Rate Limit Headers
```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1640995200
Retry-After: 60
```

## 📝 **Logging**

### Log Files
- `logs/app.log` - Application logs
- `logs/error.log` - Error logs only
- `logs/security.log` - Security events
- `logs/performance.log` - Performance metrics

### Log Format
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "logger": "api",
  "message": "User login successful",
  "user_id": 123,
  "ip_address": "192.168.1.1",
  "correlation_id": "req-12345",
  "duration_ms": 150.5,
  "endpoint": "/api/v1/login"
}
```

## 🧪 **Testing**

### Manual Testing
```bash
# Root endpoint
curl http://localhost:9000/

# Health checks
curl http://localhost:9000/health
curl http://localhost:9000/api/v1/health

# User login
curl -X POST http://localhost:9000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testadmin", "password": "admin123"}'

# User signup
curl -X POST http://localhost:9000/api/v1/signup \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "password": "Password123", "email": "newuser@example.com"}'

# Get users (requires JWT token)
curl -X GET http://localhost:9000/api/v1/users \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Get user by ID
curl -X GET http://localhost:9000/api/v1/users/1 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Refresh token
curl -X POST http://localhost:9000/api/v1/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'

# Logout
curl -X POST http://localhost:9000/api/v1/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'

# Enhanced login with session control
curl -X POST "http://localhost:9000/api/v1/login-with-session-control?session_strategy=replace_all" \
  -H "Content-Type: application/json" \
  -d '{"username": "testadmin", "password": "admin123"}'

# Get session information
curl -X GET http://localhost:9000/api/v1/sessions/info \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Revoke all other sessions
curl -X POST http://localhost:9000/api/v1/sessions/revoke-others \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Logout from all sessions
curl -X POST http://localhost:9000/api/v1/logout-all \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

### Test Users
- **Admin**: `testadmin` / `admin123`
- **User**: `testuser` / `user123`

## 🚀 **Deployment**

### Docker Deployment
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
```

### Production Checklist
- [ ] Change JWT secret key
- [ ] Configure production database
- [ ] Set up Redis cluster
- [ ] Configure log rotation
- [ ] Set up monitoring
- [ ] Configure SSL/TLS
- [ ] Set up backup strategy

## 📁 **Project Structure**

```
fastapi-user-management/
├── config/                    # Configuration management
│   └── settings.py           # Centralized settings
├── models/                    # Database models
│   └── user_model.py         # User and session models
├── routes/                    # API routes
│   ├── login.py              # Authentication endpoints
│   ├── auth_2fa.py          # 2FA endpoints
│   └── production_endpoints.py # Production API endpoints
├── schemas/                   # Pydantic schemas
│   ├── login.py              # Request/response models
│   └── auth_2fa.py           # 2FA request/response models
├── services/                 # Business logic
│   ├── auth/                 # Authentication services
│   │   ├── auth_service.py
│   │   ├── two_factor_service.py
│   │   ├── login_attempt_service.py
│   │   ├── enhanced_login_service.py
│   │   └── logout_service.py
│   ├── users/               # User management services
│   │   ├── user_service.py
│   │   ├── password_history_service.py
│   │   ├── password_reset_service.py
│   │   └── profile_update_service.py
│   ├── sessions/            # Session services
│   │   └── user_session_service.py
│   ├── permissions/         # Permission services
│   │   ├── user_permission_service.py
│   │   ├── user_group_service.py
│   │   └── api_key_service.py
│   └── audit/               # Audit services
│       └── audit_log_service.py
├── utils/                     # Utilities
│   ├── database.py          # Database configuration
│   ├── email_service.py     # Email service (SMTP)
│   ├── jwt_config.py        # JWT utilities
│   ├── redis_config.py      # Redis configuration
│   ├── logger.py            # Logging setup
│   ├── auto_refresh_middleware.py
│   ├── security_middleware.py
│   ├── rate_limit_dependency.py
│   └── loggers/             # Specialized loggers
├── templates/                 # Email templates
│   └── emails/              # HTML email templates
├── scripts/                   # Utility scripts
│   ├── backup_database.py  # Automated backups
│   ├── restore_database.py # Database restoration
│   └── migrate_2fa.py      # 2FA migration
├── tests/                    # Test suite
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── e2e/                 # End-to-end tests
├── backups/                   # Database backups
├── docs/                      # Documentation
│   ├── API_REFERENCE.md
│   └── PRODUCTION_RELEASE_PLAN.md
├── logs/                      # Log files
├── main.py                    # Application entry point
├── requirements.txt          # Python dependencies
└── pytest.ini                # Pytest configuration
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 **Author**

**Husky1711** - [GitHub](https://github.com/Husky1711)

## 🙏 **Acknowledgments**

- [FastAPI](https://fastapi.tiangolo.com/) - Modern, fast web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL toolkit
- [Redis](https://redis.io/) - In-memory data structure store
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation

---

⭐ **Star this repository if you found it helpful!**