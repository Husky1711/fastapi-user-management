# REDIS & MYSQL USAGE IN FASTAPI USER MANAGEMENT SYSTEM

## 📊 **Current System: Redis vs MySQL**

### **✅ MySQL (Primary Database)**
- **Users**: User accounts, credentials, profile
- **User Sessions**: Active sessions, device info
- **Refresh Tokens**: Refresh token records
- **Audit Logs: Security events, user actions
- Password History: Previous passwords
- User Permissions: Granular access control
- User Groups: Group membership
- API Keys: API key management

### **Redis (Currently Used For)**
- **Rate Limiting**: Key pattern `rate_limit:{endpoint}:{identifier}:{window}`
- **Cache Cleanup**: User-specific cache patterns

---

## 🔍 **Current Redis Implementation**

### **Rate Limiting (ACTIVE)**
```
Key Pattern: "rate_limit:api:v1_login:user_id:minute"
Key Pattern: "rate_limit:api:v1_profile:user_id:minute"
Key Pattern: "rate_limit:api:v1_users:user_id:minute"

Storage: Sorted Sets (ZSET)
TTL: Based on time window (60 seconds, 3600 seconds, etc.)
Purpose: Track request counts per user/IP within time windows
```

### **Cache Cleanup (ACTIVE)**
```
Key Patterns:
- "user:{user_id}:*"
- "user_session:{user_id}:*"
- "user_profile:{user_id}:*"
- "user_permissions:{user_id}:*"

Purpose: Clear user-specific cache on logout
```

---

## ❌ **NOT Currently Using Redis For:**
1. Refresh Token Storage (using MySQL instead)
2. Password Reset Tokens (using MySQL instead)
3. User Profile Caching (not implemented)
4. Session Management Caching (not implemented)
5. Audit Log Caching (not implemented)

---

## 🎯 **Recommended Redis Enhancements**

### **1. Implement Profile Caching**
```
Key: "user_profile:{user_id}"
Value: JSON string of user profile
TTL: 10 minutes
Purpose: Reduce MySQL queries for profile data

Implementation:
- Cache on profile GET
- Invalidate on profile UPDATE
- Clear on logout
```

### **2. Implement Session Caching**
```
Key: "user_session_active:{user_id}"
Value: List of active session IDs
TTL: 1 hour
Purpose: Fast session validation

Key: "session:{session_id}"
Value: Session metadata (device, IP, etc.)
TTL: 7 days
Purpose: Fast session lookup
```

### **3. Audit Log Caching**
```
Key: "audit_logs_recent:{user_id}"
Value: Recent audit logs
TTL: 5 minutes
Purpose: Fast audit log display

Key: "audit_stats:{user_id}"
Value: Statistics
TTL: 10 minutes
Purpose: Fast statistics display
```

### **4. Password Reset Token Caching**
```
Key: "password_reset:{token}"
Value: User ID
TTL: 1 hour
Purpose: Fast token validation

Implementation:
- Store in Redis for fast lookup
- Also store in MySQL for persistence
- Clear on token use
```

---

## 📊 **Redis Keys Summary (Current)**

### **Active Keys:**
```
rate_limit:api:v1_login:user_5:minute       → Counter
rate_limit:api:v1_profile:user_5:minute      → Counter
rate_limit:api:v1_users:user_5:minute       → Counter
rate_limit:api:v1_login:user_5:hour         → Counter
rate_limit:api:v1_profile:user_5:hour        → Counter
rate_limit:api:v1_users:user_5:hour         → Counter
```

### **Total Keys in Redis**: ~7-10 (all rate limiting)

---

## 💡 **Summary**

**Current State:**
- ✅ MySQL: Primary data storage
- ✅ Redis: Rate limiting only
- ❌ Redis: NOT used for caching tokens/sessions

**Recommended Improvements:**
1. Add profile caching
2. Add session caching  
3. Add audit log caching
4. Add password reset caching

**Benefits:**
- Faster API responses
- Reduced MySQL load
- Better scalability
- Improved user experience

**Next Steps:**
- Implement caching layer
- Add cache invalidation
- Monitor Redis usage
- Optimize TTL values
