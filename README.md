# 🚀 FastAPI User Management System

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.119+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black.svg)](https://black.readthedocs.io)

A production-ready, enterprise-grade user management system built with FastAPI, featuring JWT authentication, Redis-based rate limiting, multi-tenant architecture, and comprehensive logging.

## ✨ Features

### 🔐 **Authentication & Authorization**
- **JWT-based authentication** with access & refresh tokens
- **Role-based access control (RBAC)** with hierarchical permissions
- **Multi-tenant architecture** supporting organizations and users
- **Secure password hashing** with SHA-256
- **Session management** with token rotation

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
   pip install -r requirement.txt
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

## 📋 **API Endpoints**

### Authentication
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/login` | User login | 10/min, 100/hour |
| `POST` | `/api/signup` | User registration | 5/min, 50/hour |
| `POST` | `/api/refresh` | Refresh access token | 20/min, 200/hour |

### User Management
| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/api/users` | Get all users (Admin) | 5/min, 50/hour |
| `GET` | `/api/users/{id}` | Get user by ID | 20/min, 200/hour |
| `GET` | `/api/sessions` | Get user sessions | 10/min, 100/hour |
| `DELETE` | `/api/sessions/{id}` | Revoke session | 5/min, 50/hour |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/hello` | Health check |
| `GET` | `/docs` | API documentation |

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
  "endpoint": "/api/login"
}
```

## 🧪 **Testing**

### Manual Testing
```bash
# Health check
curl http://localhost:9000/hello

# User login
curl -X POST http://localhost:9000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'

# Get users (requires JWT token)
curl -X GET http://localhost:9000/api/users \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Test Users
- **Admin**: `testadmin` / `admin123`
- **User**: `testuser` / `user123`

## 🚀 **Deployment**

### Docker Deployment
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirement.txt .
RUN pip install -r requirement.txt

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
├── config/                 # Configuration management
│   ├── settings.py        # Centralized settings
│   └── env_*.txt         # Environment templates
├── models/                # Database models
│   └── user_model.py     # User and session models
├── routes/                # API routes
│   └── login.py          # Authentication endpoints
├── schemas/               # Pydantic schemas
│   └── login.py          # Request/response models
├── services/              # Business logic
│   ├── auth_service.py   # Authentication service
│   ├── user_service.py   # User management
│   └── rate_limit_service.py # Rate limiting
├── utils/                 # Utilities
│   ├── database.py       # Database configuration
│   ├── jwt_config.py     # JWT utilities
│   ├── redis_config.py   # Redis configuration
│   ├── logger.py         # Logging setup
│   └── loggers/          # Specialized loggers
├── logs/                  # Log files (auto-generated)
├── .env                   # Environment variables
├── .gitignore            # Git ignore rules
├── config_manager.py     # Configuration helper
├── main.py               # Application entry point
└── requirement.txt       # Python dependencies
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