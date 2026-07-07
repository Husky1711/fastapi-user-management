-- Sample data for Codespaces local MySQL (fastapi_users)
-- Plaintext passwords below; ensure_bcrypt_seed_passwords.py upgrades them to bcrypt after seed.
--   testadmin / admin123
--   testuser  / user123
--   testorgadmin / orgadmin123
--   test_super_admin / TestSuperAdminPass123!

USE fastapi_users;

INSERT INTO organizations (id, name, description, status)
VALUES
(1, 'Default Organization', 'Codespaces development organization', 'active'),
(2, 'System', 'Platform-level scope for super admins', 'active')
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
),
(
    'testorgadmin',
    'orgadmin@test.com',
    '7a9699d27afd56e389d65db8505223b985d66f1f0ad7062aa1193cdac5356edf',
    'active',
    '1234567890',
    'organization_admin',
    1,
    0,
    0,
    0
),
(
    'test_super_admin',
    'test_super_admin@test.com',
    'd92b308af543bcf0c01fd017a6de945a7294ae83d7c9ae7e5b98fed51c715e95',
    'active',
    '1234567890',
    'super_admin',
    2,
    0,
    0,
    0
)
ON DUPLICATE KEY UPDATE
    email = VALUES(email),
    role = VALUES(role),
    organization_id = VALUES(organization_id);

-- Ensure existing super admin is not tied to a customer organization
UPDATE users
SET organization_id = 2, role = 'super_admin'
WHERE username = 'test_super_admin';

-- testuser reports to testadmin
UPDATE users u
JOIN users mgr ON mgr.username = 'testadmin'
SET u.manager_id = mgr.id
WHERE u.username = 'testuser';
