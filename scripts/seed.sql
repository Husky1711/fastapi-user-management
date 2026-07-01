-- Sample data for Codespaces local MySQL (fastapi_users)
-- Passwords are SHA-256 hex (see utils/jwt_config.py)
--   testadmin / admin123
--   testuser  / user123

USE fastapi_users;

INSERT INTO organizations (id, name, description, status)
VALUES (1, 'Default Organization', 'Codespaces development organization', 'active')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO users (
    username,
    email,
    password,
    status,
    phone_number,
    role,
    organization_id,
    is_2fa_enabled,
    failed_login_attempts,
    login_attempts
) VALUES
(
    'testadmin',
    'admin@test.com',
    '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
    'active',
    '1234567890',
    'admin',
    1,
    0,
    0,
    0
),
(
    'testuser',
    'user@test.com',
    'e606e38b0d8c19b24cf0ee3808183162ea7cd63ff7912dbb22b5e803286b4446',
    'active',
    '1234567890',
    'user',
    1,
    0,
    0,
    0
)
ON DUPLICATE KEY UPDATE email = VALUES(email);
