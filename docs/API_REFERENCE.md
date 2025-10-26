# 📋 **Complete API Reference**

## **🔐 Authentication & Authorization APIs**

### **Core Authentication**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/v1/login` | User login with JWT tokens | 10/min, 100/hour |
| `POST` | `/api/v1/signup` | User registration | 5/min, 50/hour |
| `POST` | `/api/v1/refresh` | Refresh access token | 20/min, 200/hour |
| `POST` | `/api/v1/logout` | User logout (single session) | 20/min, 200/hour |
| `POST` | `/api/v1/logout-all` | Logout from all sessions | 5/min, 50/hour |

### **Advanced Session Management**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/v1/login-with-session-control` | Login with session strategy | 10/min, 100/hour |
| `GET` | `/api/v1/sessions/info` | Get current session info | 30/min, 300/hour |
| `POST` | `/api/v1/sessions/revoke-others` | Revoke other sessions | 5/min, 50/hour |
| `GET` | `/api/v1/sessions` | Get user sessions | 30/min, 300/hour |
| `DELETE` | `/api/v1/sessions/{session_id}` | Delete specific session | 10/min, 100/hour |

### **Debug Endpoints**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/v1/debug-login` | Debug login endpoint | 20/min, 200/hour |
| `POST` | `/api/v1/debug-refresh` | Debug refresh endpoint | 20/min, 200/hour |

---

## **👥 User Management APIs**

### **User Operations**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/users` | Get all users (Admin only) | 30/min, 300/hour |
| `GET` | `/api/v1/users/{user_id}` | Get specific user | 30/min, 300/hour |
| `POST` | `/api/v1/admin/users/create` | Create user (Admin only) | 10/min, 100/hour |

### **Profile Management**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/profile` | Get user profile | 30/min, 300/hour |
| `PUT` | `/api/v1/profile` | Update user profile | 10/min, 100/hour |

---

## **🔑 Password Management APIs**

### **Password Operations**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/v1/password/change` | Change password | 5/min, 50/hour |
| `POST` | `/api/v1/password/reset-request` | Request password reset | 3/min, 30/hour |
| `POST` | `/api/v1/password/reset` | Confirm password reset | 5/min, 50/hour |
| `GET` | `/api/v1/password/reset/validate/{token}` | Validate reset token | 10/min, 100/hour |

### **Password History**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/password/history` | Get password history | 30/min, 300/hour |
| `GET` | `/api/v1/password/policy-stats` | Get password policy stats | 30/min, 300/hour |

---

## **📊 Production Features APIs**

### **Audit & Compliance**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/audit/logs` | Get audit logs | 30/min, 300/hour |
| `GET` | `/api/v1/audit/statistics` | Get audit statistics | 30/min, 300/hour |

### **Session Management**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/sessions` | Get user sessions | 30/min, 300/hour |
| `GET` | `/api/v1/sessions/statistics` | Get session statistics | 30/min, 300/hour |
| `POST` | `/api/v1/sessions/cleanup` | Clean up expired sessions | 5/min, 50/hour |

### **Permissions Management**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/permissions` | Get user permissions | 30/min, 300/hour |
| `GET` | `/api/v1/permissions/standard` | Get standard permissions | 30/min, 300/hour |
| `GET` | `/api/v1/permissions/statistics` | Get permission statistics | 30/min, 300/hour |

### **Groups Management**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/groups` | Get organization groups | 30/min, 300/hour |
| `GET` | `/api/v1/groups/{group_id}/members` | Get group members | 30/min, 300/hour |
| `GET` | `/api/v1/groups/statistics` | Get group statistics | 30/min, 300/hour |

### **API Keys Management**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/api-keys` | Get user API keys | 30/min, 300/hour |
| `GET` | `/api/v1/api-keys/standard-permissions` | Get standard API permissions | 30/min, 300/hour |
| `GET` | `/api/v1/api-keys/statistics` | Get API key statistics | 30/min, 300/hour |

---

## **🏥 System APIs**

### **Health & Monitoring**
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/v1/health` | Health check endpoint | 60/min, 600/hour |
| `GET` | `/` | Root endpoint | 60/min, 600/hour |

---

## **📈 API Summary**

### **Total Endpoints: 35**
- **Authentication**: 7 endpoints
- **User Management**: 5 endpoints  
- **Password Management**: 6 endpoints
- **Production Features**: 15 endpoints
- **System**: 2 endpoints

### **Rate Limiting**
- **Global IP Limit**: 1000 requests/hour
- **Per-endpoint limits**: Vary by endpoint (3-60 requests/min)
- **Authentication endpoints**: Stricter limits (3-20 requests/min)
- **Read-only endpoints**: Higher limits (30-60 requests/min)

### **Authentication Required**
- **All endpoints** except `/api/v1/login`, `/api/v1/signup`, `/api/v1/password/reset-request`, `/api/v1/password/reset/validate/{token}`, and `/api/v1/health`
- **JWT Bearer token** required in Authorization header
- **Role-based access control** for admin endpoints

### **Response Formats**
- **Success responses**: JSON with data
- **Error responses**: JSON with error details
- **Pagination**: Available for list endpoints
- **Filtering**: Available for audit logs and sessions
