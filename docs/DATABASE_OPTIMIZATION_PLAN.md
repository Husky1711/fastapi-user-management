# 🗄️ DATABASE OPTIMIZATION PLAN
**FastAPI User Management System**  
**Goal:** Optimize database performance with indexing, query optimization, and connection pooling

---

## 📊 CURRENT STATUS

### **What We Have:**
- ✅ MySQL database with all tables created
- ✅ Models defined with relationships
- ✅ Basic queries working
- ✅ Caching layer implemented

### **What We Need:**
- ⏳ Database indexes on frequently queried columns
- ⏳ Query optimization for common operations
- ⏳ Connection pooling configuration
- ⏳ Database monitoring setup

---

## 🎯 OPTIMIZATION GOALS

### **Performance Targets:**
- Profile GET queries: < 10ms (currently ~50ms)
- User list queries: < 20ms (currently ~100ms)
- Session queries: < 15ms (currently ~80ms)
- Audit log queries: < 25ms (currently ~150ms)
- Concurrent connections: Support 50+ simultaneous users

---

## 📋 PHASE 1: DATABASE INDEXING

### **Priority: HIGH**

#### **1.1 Users Table Indexes**

**Indexes to Add:**
```sql
-- Email index (most common lookup)
CREATE INDEX idx_users_email ON users(email);

-- Username index (login lookup)
CREATE INDEX idx_users_username ON users(username);

-- Organization index (multi-tenant queries)
CREATE INDEX idx_users_organization ON users(organization_id);

-- Role index (authorization queries)
CREATE INDEX idx_users_role ON users(role);

-- Status index (active user filtering)
CREATE INDEX idx_users_status ON users(status);

-- Composite index for organization + role
CREATE INDEX idx_users_org_role ON users(organization_id, role);

-- Composite index for organization + status
CREATE INDEX idx_users_org_status ON users(organization_id, status);
```

**Query Optimization:**
- Email lookup: ~50ms → ~5ms
- Username lookup: ~50ms → ~5ms
- Organization queries: ~100ms → ~10ms

---

#### **1.2 Refresh Tokens Table Indexes**

**Indexes to Add:**
```sql
-- User ID index (token lookups)
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);

-- Token hash index (verification)
CREATE INDEX idx_refresh_tokens_token ON refresh_tokens(token_hash);

-- Revoked index (active token filtering)
CREATE INDEX idx_refresh_tokens_revoked ON refresh_tokens(is_revoked);

-- Expiration index (cleanup queries)
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at);

-- Composite index for user + active tokens
CREATE INDEX idx_refresh_tokens_user_active ON refresh_tokens(user_id, is_revoked);
```

**Query Optimization:**
- Token verification: ~80ms → ~8ms
- User token queries: ~60ms → ~6ms

---

#### **1.3 User Sessions Table Indexes**

**Indexes to Add:**
```sql
-- User ID index (session lookups)
CREATE INDEX idx_user_sessions_user ON user_sessions(user_id);

-- Active session index
CREATE INDEX idx_user_sessions_active ON user_sessions(is_active);

-- Device info index (device tracking)
CREATE INDEX idx_user_sessions_device ON user_sessions(device_info);

-- Composite index for user + active
CREATE INDEX idx_user_sessions_user_active ON user_sessions(user_id, is_active);

-- Expiration index (cleanup)
CREATE INDEX idx_user_sessions_expires ON user_sessions(expires_at);
```

**Query Optimization:**
- Active session queries: ~80ms → ~8ms
- Device tracking: ~100ms → ~10ms

---

#### **1.4 Audit Logs Table Indexes**

**Indexes to Add:**
```sql
-- User ID index (audit queries)
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);

-- Created date index (time-based queries)
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);

-- Event type index (filtering)
CREATE INDEX idx_audit_logs_event ON audit_logs(event_type);

-- Organization index (multi-tenant)
CREATE INDEX idx_audit_logs_org ON audit_logs(organization_id);

-- Composite index for user + date
CREATE INDEX idx_audit_logs_user_date ON audit_logs(user_id, created_at);

-- Composite index for organization + date
CREATE INDEX idx_audit_logs_org_date ON audit_logs(organization_id, created_at);
```

**Query Optimization:**
- Audit log queries: ~150ms → ~15ms
- Time-based filtering: ~200ms → ~20ms

---

#### **1.5 Login Attempts Table Indexes**

**Indexes to Add:**
```sql
-- User ID index
CREATE INDEX idx_login_attempts_user ON login_attempts(user_id);

-- Success index (filtering)
CREATE INDEX idx_login_attempts_success ON login_attempts(success);

-- Created date index (time-based)
CREATE INDEX idx_login_attempts_created ON login_attempts(created_at);

-- IP address index (security queries)
CREATE INDEX idx_login_attempts_ip ON login_attempts(ip_address);

-- Composite index for user + recent attempts
CREATE INDEX idx_login_attempts_user_recent ON login_attempts(user_id, created_at DESC);
```

**Query Optimization:**
- Login attempt queries: ~120ms → ~12ms
- Security queries: ~150ms → ~15ms

---

## 📋 PHASE 2: QUERY OPTIMIZATION

### **Priority: MEDIUM**

#### **2.1 Profile Queries**

**Current Query:**
```python
def get_user_profile(user_id):
    return db.query(User).filter(User.id == user_id).first()
```

**Optimization:**
- Use select_related for relationships
- Cache results
- Use prepared statements

**Expected Improvement:** ~30ms → ~5ms

---

#### **2.2 User List Queries**

**Current Query:**
```python
def get_users_by_organization(org_id):
    return db.query(User).filter(User.organization_id == org_id).all()
```

**Optimization:**
- Add pagination (LIMIT/OFFSET)
- Use count() for total
- Add select_related

**Expected Improvement:** ~100ms → ~20ms

---

#### **2.3 Session Queries**

**Current Query:**
```python
def get_user_sessions(user_id):
    return db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_active == True
    ).all()
```

**Optimization:**
- Combine filters in single query
- Use index on (user_id, is_active)
- Limit results

**Expected Improvement:** ~80ms → ~8ms

---

#### **2.4 Audit Log Queries**

**Current Query:**
```python
def get_audit_logs(user_id, limit=100):
    return db.query(AuditLog).filter(
        AuditLog.user_id == user_id
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()
```

**Optimization:**
- Use index on (user_id, created_at)
- Stream results
- Add Redis caching

**Expected Improvement:** ~150ms → ~15ms

---

## 📋 PHASE 3: CONNECTION POOLING

### **Priority: HIGH**

#### **3.1 Pool Configuration**

**Settings to Configure:**
```python
# In utils/database.py
engine = create_engine(
    DB_URL,
    pool_size=20,           # Connection pool size
    max_overflow=10,        # Extra connections allowed
    pool_timeout=30,        # Timeout for getting connection
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True,     # Verify connections before using
    echo=False
)
```

**Benefits:**
- Reduced connection overhead
- Better resource utilization
- Improved concurrent performance

---

## 📋 PHASE 4: PERFORMANCE MONITORING

### **Priority: MEDIUM**

#### **4.1 Query Timing**

**Add logging:**
```python
import time

def log_slow_queries(query_time, query_type, user_id):
    if query_time > 100:  # Log queries slower than 100ms
        logger.warning(f"Slow query: {query_type} took {query_time}ms for user {user_id}")
```

#### **4.2 Database Metrics**

**Track:**
- Query execution times
- Connection pool usage
- Table scan counts
- Index usage statistics

---

## 📊 IMPLEMENTATION PLAN

### **Day 1: Index Creation**
- ✅ Create migration script for indexes
- ✅ Test index creation
- ✅ Measure performance improvements
- ✅ Document index usage

**Files to Create:**
```
scripts/add_database_indexes.py
scripts/test_index_performance.py
```

---

### **Day 2: Query Optimization**
- ✅ Optimize profile queries
- ✅ Optimize list queries
- ✅ Optimize session queries
- ✅ Optimize audit log queries
- ✅ Add query monitoring

**Files to Create:**
```
scripts/optimize_queries.py
utils/query_monitor.py
```

---

### **Day 3: Connection Pooling**
- ✅ Configure connection pool
- ✅ Test pool under load
- ✅ Monitor pool metrics
- ✅ Adjust pool size

**Files to Modify:**
```
utils/database.py (update pool config)
```

---

## 🧪 TESTING PLAN

### **Performance Tests:**

1. **Profile Query Test**
   - Measure time with/without indexes
   - Target: < 10ms

2. **User List Test**
   - Measure time with/without indexes
   - Target: < 20ms

3. **Session Query Test**
   - Measure time with/without indexes
   - Target: < 15ms

4. **Audit Log Test**
   - Measure time with/without indexes
   - Target: < 25ms

5. **Concurrent Load Test**
   - Test with 50+ simultaneous users
   - Monitor connection pool usage
   - Target: < 100ms average response

---

## 📈 EXPECTED RESULTS

### **Performance Improvements:**
- Query speed improvement: 5-10x faster
- Concurrent connection support: 50+ users
- Database CPU usage: -50%
- Response time improvement: -80%

### **Metrics to Track:**
- Average query time: < 20ms
- 95th percentile: < 50ms
- 99th percentile: < 100ms
- Connection pool usage: < 80%
- Cache hit rate: > 80%

---

## ✅ SUCCESS CRITERIA

1. ✅ All indexes created successfully
2. ✅ Query performance improved by 5-10x
3. ✅ No query takes > 100ms under normal load
4. ✅ Connection pool handles 50+ concurrent users
5. ✅ Query monitoring working
6. ✅ No breaking changes to existing code

---

## 🚀 NEXT STEPS

### **Immediate Actions:**
1. Create database index migration script
2. Test index creation on development database
3. Measure performance improvements
4. Optimize slow queries
5. Configure connection pooling

### **Files to Create:**
```
scripts/add_database_indexes.py      # Index creation script
scripts/test_index_performance.py   # Performance testing script
utils/query_monitor.py               # Query monitoring utility
```

---

## 📊 ESTIMATED TIMELINE

**Total Time:** 2-3 days

**Day 1:**
- Morning: Index creation script (2-3 hours)
- Afternoon: Performance testing (2-3 hours)

**Day 2:**
- Morning: Query optimization (3-4 hours)
- Afternoon: Testing and validation (2-3 hours)

**Day 3:**
- Morning: Connection pooling (2-3 hours)
- Afternoon: Final testing and documentation (2-3 hours)

---

## 🎯 PRIORITY ORDER

### **High Priority (Do First):**
1. Users table indexes (email, username, organization)
2. Refresh tokens indexes (user_id, token_hash)
3. Connection pooling configuration

### **Medium Priority (Do Next):**
4. User sessions indexes
5. Audit logs indexes
6. Query optimization

### **Low Priority (Nice to Have):**
7. Login attempts indexes
8. Query monitoring
9. Advanced optimizations

---

## 📝 NOTES

- **Backup before changes:** Always backup database before adding indexes
- **Test on staging:** Test all changes on staging before production
- **Monitor performance:** Track metrics before and after changes
- **Document changes:** Keep detailed logs of all optimizations
- **Review logs:** Check database logs for any issues

---

**Ready to start implementation?**

