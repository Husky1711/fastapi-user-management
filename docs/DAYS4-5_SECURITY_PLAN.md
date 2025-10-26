# 🔐 Days 4-5: Security Hardening (2FA) - Implementation Plan

## 🎯 **Goal:**
Implement Two-Factor Authentication (2FA) with TOTP (Time-based One-Time Password) using Google Authenticator or similar apps

## 📋 **Features to Implement:**

### **1. Two-Factor Authentication (2FA)**
- TOTP-based 2FA (Google Authenticator compatible)
- QR code generation for setup
- Backup codes for recovery
- Optional 2FA (users can enable/disable)
- Admin can require 2FA for organization

### **2. Login Attempt Tracking**
- Track failed login attempts per user
- Lock account after X failed attempts
- Automatic lockout duration (15 minutes)
- Email notification on account lockout
- IP address tracking for suspicious activity

### **3. Account Lockout System**
- Automatic lockout after 5 failed attempts
- 15-minute lockout duration
- Manual unlock by admin
- Audit logging of lockout events

## 🔧 **Technical Implementation:**

### **Step 1: Install Required Packages**
```bash
pip install pyotp qrcode[pil] pillow
```

### **Step 2: Create Database Tables**
```sql
-- Add 2FA columns to users table
ALTER TABLE users ADD COLUMN is_2fa_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN two_factor_secret VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN failed_login_attempts INT DEFAULT 0;
ALTER TABLE users ADD COLUMN locked_until DATETIME NULL;

-- Create login attempts table
CREATE TABLE login_attempts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN,
    failure_reason VARCHAR(255),
    created_at DATETIME DEFAULT NOW(),
    INDEX idx_user_id (user_id),
    INDEX idx_ip (ip_address),
    INDEX idx_created (created_at)
);
```

### **Step 3: Create 2FA Service**
- `services/auth/two_factor_service.py`
- QR code generation
- TOTP verification
- Backup code management

### **Step 4: Update Login Endpoint**
- Check if 2FA is enabled
- If enabled, require TOTP code
- Track login attempts
- Implement lockout

### **Step 5: Add 2FA Management Endpoints**
- `POST /api/v1/2fa/enable` - Enable 2FA
- `POST /api/v1/2fa/disable` - Disable 2FA
- `POST /api/v1/2fa/verify` - Verify 2FA code
- `GET /api/v1/2fa/qrcode` - Get QR code

### **Step 6: Security Headers**
- Update security middleware
- Add CSP headers
- Add X-Frame-Options
- Add X-Content-Type-Options

## 📝 **Files to Create:**

1. `services/auth/two_factor_service.py` - 2FA implementation
2. `routes/auth_2fa.py` - 2FA endpoints
3. `schemas/auth_2fa.py` - 2FA schemas
4. Database migration script
5. Test suite for 2FA

## ✅ **Success Criteria:**

1. ✅ Users can enable/disable 2FA
2. ✅ QR code generation working
3. ✅ TOTP verification working
4. ✅ Login attempts tracked
5. ✅ Account lockout working
6. ✅ Email notifications on lockout
7. ✅ All features tested

## 🚀 **Ready to Start?**

**Estimated Time: 2-3 hours**

Should I proceed with implementation? 🚀
