-- =============================================================================
-- FastAPI User Management — latest database schema (DDL only)
-- Generated: 2026-07-16 04:21:17 UTC
-- Database: fastapi_users
-- Alembic revision: 20260716_soft_unique
-- Source: live MySQL via SHOW CREATE TABLE (no data)
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE DATABASE IF NOT EXISTS `fastapi_users` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `fastapi_users`;

-- ---------------------------------------------------------------------------
-- Table: `alembic_version`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `alembic_version`;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `api_keys`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `api_keys`;
CREATE TABLE `api_keys` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `organization_id` int NOT NULL,
  `key_name` varchar(100) NOT NULL,
  `key_hash` varchar(255) NOT NULL,
  `key_prefix` varchar(20) NOT NULL,
  `permissions` json DEFAULT NULL,
  `rate_limit_per_minute` int DEFAULT NULL,
  `rate_limit_per_hour` int DEFAULT NULL,
  `last_used_at` datetime DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime DEFAULT (now()),
  `created_by` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_api_keys_key_hash` (`key_hash`),
  KEY `ix_api_keys_expires_at` (`expires_at`),
  KEY `ix_api_keys_created_at` (`created_at`),
  KEY `ix_api_keys_organization_id` (`organization_id`),
  KEY `ix_api_keys_last_used_at` (`last_used_at`),
  KEY `ix_api_keys_created_by` (`created_by`),
  KEY `ix_api_keys_key_prefix` (`key_prefix`),
  KEY `ix_api_keys_key_name` (`key_name`),
  KEY `ix_api_keys_is_active` (`is_active`),
  KEY `ix_api_keys_id` (`id`),
  KEY `ix_api_keys_user_id` (`user_id`),
  KEY `idx_api_keys_org_active` (`organization_id`,`is_active`),
  CONSTRAINT `fk_api_keys_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_api_keys_organization_id` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_api_keys_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `audit_logs`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `organization_id` int DEFAULT NULL,
  `event_type` varchar(50) NOT NULL,
  `event_category` varchar(30) DEFAULT NULL,
  `resource_type` varchar(50) DEFAULT NULL,
  `resource_id` int DEFAULT NULL,
  `action` varchar(50) DEFAULT NULL,
  `old_values` json DEFAULT NULL,
  `new_values` json DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` text,
  `request_id` varchar(100) DEFAULT NULL,
  `correlation_id` varchar(100) DEFAULT NULL,
  `status` enum('success','failure','error') DEFAULT NULL,
  `error_message` text,
  `log_metadata` json DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_audit_logs_correlation_id` (`correlation_id`),
  KEY `ix_audit_logs_resource_id` (`resource_id`),
  KEY `ix_audit_logs_ip_address` (`ip_address`),
  KEY `ix_audit_logs_created_at` (`created_at`),
  KEY `ix_audit_logs_action` (`action`),
  KEY `ix_audit_logs_request_id` (`request_id`),
  KEY `ix_audit_logs_event_category` (`event_category`),
  KEY `ix_audit_logs_status` (`status`),
  KEY `ix_audit_logs_resource_type` (`resource_type`),
  KEY `idx_audit_logs_org_created` (`organization_id`,`created_at`),
  KEY `idx_audit_logs_user_created` (`user_id`,`created_at`),
  KEY `idx_audit_logs_event_created` (`event_type`,`created_at`),
  CONSTRAINT `fk_audit_logs_organization_id` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_audit_logs_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=247 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `consent_records`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `consent_records`;
CREATE TABLE `consent_records` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `organization_id` int DEFAULT NULL,
  `consent_type` varchar(100) NOT NULL,
  `granted` tinyint(1) NOT NULL DEFAULT '1',
  `granted_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `source` varchar(100) DEFAULT NULL,
  `details` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `policy_version` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_consent_records_user_id` (`user_id`),
  KEY `ix_consent_records_organization_id` (`organization_id`),
  KEY `ix_consent_records_consent_type` (`consent_type`),
  CONSTRAINT `consent_records_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_consent_records_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `data_retention_policies`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `data_retention_policies`;
CREATE TABLE `data_retention_policies` (
  `id` int NOT NULL AUTO_INCREMENT,
  `table_name` varchar(100) NOT NULL,
  `retention_days` int NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `description` varchar(255) DEFAULT NULL,
  `updated_by` int DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_data_retention_table_name` (`table_name`),
  KEY `updated_by` (`updated_by`),
  KEY `ix_data_retention_policies_table_name` (`table_name`),
  KEY `ix_data_retention_policies_is_active` (`is_active`),
  CONSTRAINT `data_retention_policies_ibfk_1` FOREIGN KEY (`updated_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `email_verification_tokens`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `email_verification_tokens`;
CREATE TABLE `email_verification_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `email` varchar(255) NOT NULL,
  `token_hash` varchar(255) NOT NULL,
  `expires_at` datetime NOT NULL,
  `verified_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_evt_token_hash` (`token_hash`),
  KEY `idx_evt_user_expires` (`user_id`,`expires_at`),
  CONSTRAINT `fk_evt_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `group_permissions`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `group_permissions`;
CREATE TABLE `group_permissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  `granted_by` int DEFAULT NULL,
  `granted_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_group_permissions` (`group_id`,`permission_id`),
  KEY `granted_by` (`granted_by`),
  KEY `ix_group_permissions_group_id` (`group_id`),
  KEY `ix_group_permissions_permission_id` (`permission_id`),
  CONSTRAINT `group_permissions_ibfk_1` FOREIGN KEY (`group_id`) REFERENCES `user_groups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `group_permissions_ibfk_2` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `group_permissions_ibfk_3` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `login_attempts`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `login_attempts`;
CREATE TABLE `login_attempts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `username` varchar(255) NOT NULL,
  `ip_address` varchar(45) NOT NULL,
  `user_agent` text,
  `success` tinyint(1) NOT NULL DEFAULT '0',
  `failure_reason` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_login_attempts_success` (`success`),
  KEY `ix_login_attempts_created_at` (`created_at`),
  KEY `ix_login_attempts_user_id` (`user_id`),
  KEY `idx_login_attempts_ip_created` (`ip_address`,`created_at`),
  KEY `idx_login_attempts_username_created` (`username`,`created_at`),
  CONSTRAINT `fk_login_attempts_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=473 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `organization_settings`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `organization_settings`;
CREATE TABLE `organization_settings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `organization_id` int NOT NULL,
  `setting_key` varchar(100) NOT NULL,
  `setting_value` text NOT NULL,
  `updated_by` int DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_org_settings_key` (`organization_id`,`setting_key`),
  KEY `updated_by` (`updated_by`),
  KEY `ix_organization_settings_organization_id` (`organization_id`),
  KEY `ix_organization_settings_setting_key` (`setting_key`),
  CONSTRAINT `organization_settings_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `organization_settings_ibfk_2` FOREIGN KEY (`updated_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `organizations`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `organizations`;
CREATE TABLE `organizations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` text,
  `status` enum('active','inactive','suspended') NOT NULL DEFAULT 'active',
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  `slug` varchar(100) NOT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `deleted_by` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_organizations_name_active` (((case when (`deleted_at` is null) then `name` end))),
  UNIQUE KEY `uq_organizations_slug_active` (((case when (`deleted_at` is null) then `slug` end))),
  KEY `fk_organizations_deleted_by` (`deleted_by`),
  KEY `idx_organizations_deleted_at` (`deleted_at`),
  KEY `ix_organizations_name` (`name`),
  KEY `ix_organizations_slug` (`slug`),
  CONSTRAINT `fk_organizations_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `password_history`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `password_history`;
CREATE TABLE `password_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `changed_by` int DEFAULT NULL,
  `change_reason` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_password_history_change_reason` (`change_reason`),
  KEY `ix_password_history_changed_by` (`changed_by`),
  KEY `ix_password_history_id` (`id`),
  KEY `ix_password_history_user_id` (`user_id`),
  KEY `ix_password_history_created_at` (`created_at`),
  KEY `idx_password_history_user_created` (`user_id`,`created_at`),
  CONSTRAINT `fk_password_history_changed_by` FOREIGN KEY (`changed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_password_history_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `password_reset_tokens`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `password_reset_tokens`;
CREATE TABLE `password_reset_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `token_hash` varchar(255) NOT NULL,
  `expires_at` datetime NOT NULL,
  `used_at` datetime DEFAULT NULL,
  `requested_ip` varchar(45) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_prt_token_hash` (`token_hash`),
  KEY `idx_prt_user_expires` (`user_id`,`expires_at`),
  CONSTRAINT `fk_prt_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `permissions`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `permissions`;
CREATE TABLE `permissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `category` varchar(50) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_permissions_name` (`name`),
  KEY `ix_permissions_name` (`name`),
  KEY `ix_permissions_category` (`category`)
) ENGINE=InnoDB AUTO_INCREMENT=55 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `refresh_tokens`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `refresh_tokens`;
CREATE TABLE `refresh_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `token_hash` varchar(255) NOT NULL,
  `expires_at` datetime NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `device_info` text,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` text,
  `is_revoked` tinyint(1) NOT NULL DEFAULT '0',
  `revoked_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token_hash` (`token_hash`),
  KEY `idx_refresh_tokens_user_revoked_expires` (`user_id`,`is_revoked`,`expires_at`),
  CONSTRAINT `fk_refresh_tokens_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=275 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `role_permissions`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `role_permissions`;
CREATE TABLE `role_permissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `role_id` int NOT NULL,
  `permission_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_role_permissions` (`role_id`,`permission_id`),
  KEY `ix_role_permissions_role_id` (`role_id`),
  KEY `ix_role_permissions_permission_id` (`permission_id`),
  CONSTRAINT `role_permissions_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `role_permissions_ibfk_2` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=111 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `roles`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `organization_id` int DEFAULT NULL,
  `org_scope_key` int NOT NULL DEFAULT '0',
  `is_system` tinyint(1) NOT NULL DEFAULT '0',
  `description` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_roles_name_org_scope` (`name`,`org_scope_key`),
  KEY `ix_roles_name` (`name`),
  KEY `ix_roles_organization_id` (`organization_id`),
  KEY `ix_roles_is_system` (`is_system`),
  CONSTRAINT `roles_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `security_incidents`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `security_incidents`;
CREATE TABLE `security_incidents` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `organization_id` int DEFAULT NULL,
  `incident_type` varchar(100) NOT NULL,
  `severity` varchar(20) NOT NULL DEFAULT 'medium',
  `details` text,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` text,
  `resolved_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_security_incidents_user_id` (`user_id`),
  KEY `ix_security_incidents_organization_id` (`organization_id`),
  KEY `ix_security_incidents_incident_type` (`incident_type`),
  KEY `ix_security_incidents_severity` (`severity`),
  KEY `ix_security_incidents_created_at` (`created_at`),
  CONSTRAINT `security_incidents_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `security_incidents_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `user_group_memberships`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `user_group_memberships`;
CREATE TABLE `user_group_memberships` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  `added_by` int NOT NULL,
  `added_at` datetime DEFAULT (now()),
  `expires_at` datetime DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_group_membership` (`user_id`,`group_id`),
  KEY `ix_user_group_memberships_is_active` (`is_active`),
  KEY `ix_user_group_memberships_group_id` (`group_id`),
  KEY `ix_user_group_memberships_expires_at` (`expires_at`),
  KEY `ix_user_group_memberships_added_by` (`added_by`),
  KEY `ix_user_group_memberships_id` (`id`),
  KEY `ix_user_group_memberships_user_id` (`user_id`),
  KEY `ix_user_group_memberships_added_at` (`added_at`),
  CONSTRAINT `fk_user_group_memberships_added_by` FOREIGN KEY (`added_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_user_group_memberships_group_id` FOREIGN KEY (`group_id`) REFERENCES `user_groups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_group_memberships_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `user_groups`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `user_groups`;
CREATE TABLE `user_groups` (
  `id` int NOT NULL AUTO_INCREMENT,
  `organization_id` int NOT NULL,
  `name` varchar(100) NOT NULL,
  `description` text,
  `created_by` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_groups_org_name` (`organization_id`,`name`),
  KEY `ix_user_groups_created_by` (`created_by`),
  KEY `ix_user_groups_created_at` (`created_at`),
  KEY `ix_user_groups_name` (`name`),
  KEY `ix_user_groups_id` (`id`),
  KEY `ix_user_groups_is_active` (`is_active`),
  KEY `ix_user_groups_organization_id` (`organization_id`),
  CONSTRAINT `fk_user_groups_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_user_groups_organization_id` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=34 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `user_invitations`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `user_invitations`;
CREATE TABLE `user_invitations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `organization_id` int NOT NULL,
  `email` varchar(255) NOT NULL,
  `role` enum('user','admin','organization_admin','super_admin') NOT NULL DEFAULT 'user',
  `token_hash` varchar(255) NOT NULL,
  `invited_by` int NOT NULL,
  `expires_at` datetime NOT NULL,
  `accepted_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_inv_token_hash` (`token_hash`),
  UNIQUE KEY `uq_inv_one_pending_org_email` (((case when ((`accepted_at` is null) and (`revoked_at` is null)) then `organization_id` end)),((case when ((`accepted_at` is null) and (`revoked_at` is null)) then `email` end))),
  KEY `fk_inv_invited_by` (`invited_by`),
  KEY `idx_inv_org_email` (`organization_id`,`email`),
  KEY `idx_inv_expires` (`expires_at`),
  CONSTRAINT `fk_inv_invited_by` FOREIGN KEY (`invited_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_inv_org` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `user_permissions`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `user_permissions`;
CREATE TABLE `user_permissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_name` varchar(100) NOT NULL,
  `resource_type` varchar(50) NOT NULL DEFAULT '',
  `resource_id` int NOT NULL DEFAULT '0',
  `granted_by` int DEFAULT NULL,
  `granted_at` datetime DEFAULT (now()),
  `expires_at` datetime DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `organization_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_permission_grant` (`user_id`,`organization_id`,`permission_id`,`resource_type`,`resource_id`),
  KEY `ix_user_permissions_expires_at` (`expires_at`),
  KEY `ix_user_permissions_id` (`id`),
  KEY `ix_user_permissions_permission_name` (`permission_name`),
  KEY `ix_user_permissions_resource_type` (`resource_type`),
  KEY `ix_user_permissions_user_id` (`user_id`),
  KEY `ix_user_permissions_granted_by` (`granted_by`),
  KEY `ix_user_permissions_granted_at` (`granted_at`),
  KEY `ix_user_permissions_is_active` (`is_active`),
  KEY `ix_user_permissions_resource_id` (`resource_id`),
  KEY `ix_user_permissions_organization_id` (`organization_id`),
  KEY `ix_user_permissions_permission_id` (`permission_id`),
  CONSTRAINT `fk_user_permissions_granted_by` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_user_permissions_organization_id` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_permissions_permission_id` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_user_permissions_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `user_roles`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `user_roles`;
CREATE TABLE `user_roles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `role_id` int NOT NULL,
  `granted_by` int DEFAULT NULL,
  `granted_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_roles` (`user_id`,`role_id`),
  KEY `granted_by` (`granted_by`),
  KEY `ix_user_roles_user_id` (`user_id`),
  KEY `ix_user_roles_role_id` (`role_id`),
  CONSTRAINT `user_roles_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_roles_ibfk_2` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_roles_ibfk_3` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `user_sessions`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `user_sessions`;
CREATE TABLE `user_sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `session_id` varchar(255) NOT NULL,
  `access_token_hash` varchar(255) DEFAULT NULL,
  `refresh_token_id` int DEFAULT NULL,
  `device_fingerprint` varchar(255) DEFAULT NULL,
  `device_name` varchar(100) DEFAULT NULL,
  `device_type` varchar(50) DEFAULT NULL,
  `browser_name` varchar(50) DEFAULT NULL,
  `browser_version` varchar(20) DEFAULT NULL,
  `os_name` varchar(50) DEFAULT NULL,
  `os_version` varchar(20) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `country` varchar(50) DEFAULT NULL,
  `city` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `last_activity` datetime DEFAULT (now()),
  `created_at` datetime DEFAULT (now()),
  `expires_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_user_sessions_session_id` (`session_id`),
  KEY `ix_user_sessions_refresh_token_id` (`refresh_token_id`),
  KEY `ix_user_sessions_is_active` (`is_active`),
  KEY `ix_user_sessions_created_at` (`created_at`),
  KEY `ix_user_sessions_id` (`id`),
  KEY `ix_user_sessions_device_fingerprint` (`device_fingerprint`),
  KEY `ix_user_sessions_ip_address` (`ip_address`),
  KEY `ix_user_sessions_last_activity` (`last_activity`),
  KEY `ix_user_sessions_user_id` (`user_id`),
  KEY `ix_user_sessions_expires_at` (`expires_at`),
  KEY `idx_user_sessions_user_active_expires` (`user_id`,`is_active`,`expires_at`),
  CONSTRAINT `fk_user_sessions_refresh_token_id` FOREIGN KEY (`refresh_token_id`) REFERENCES `refresh_tokens` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_user_sessions_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=275 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ---------------------------------------------------------------------------
-- Table: `users`
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `status` enum('active','inactive','suspended','pending') NOT NULL DEFAULT 'active',
  `phone_number` varchar(20) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `locked_until` datetime DEFAULT NULL,
  `is_2fa_enabled` tinyint(1) NOT NULL DEFAULT '0',
  `two_factor_secret` varchar(255) DEFAULT NULL,
  `backup_codes` json DEFAULT NULL,
  `failed_login_attempts` int NOT NULL DEFAULT '0',
  `role` enum('user','admin','organization_admin','super_admin') NOT NULL DEFAULT 'user',
  `organization_id` int NOT NULL,
  `manager_id` int DEFAULT NULL,
  `email_verified_at` datetime DEFAULT NULL,
  `password_changed_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL,
  `deleted_by` int DEFAULT NULL,
  `backup_codes_generated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email_active` (((case when (`deleted_at` is null) then `email` end))),
  UNIQUE KEY `uq_users_username_active` (((case when (`deleted_at` is null) then `username` end))),
  KEY `ix_users_is_2fa_enabled` (`is_2fa_enabled`),
  KEY `ix_users_manager_id` (`manager_id`),
  KEY `fk_users_deleted_by` (`deleted_by`),
  KEY `idx_users_org_status` (`organization_id`,`status`),
  KEY `idx_users_org_role` (`organization_id`,`role`),
  KEY `idx_users_deleted_at` (`deleted_at`),
  KEY `ix_users_email` (`email`),
  KEY `ix_users_username` (`username`),
  CONSTRAINT `fk_users_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_users_manager_id` FOREIGN KEY (`manager_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_users_organization_id` FOREIGN KEY (`organization_id`) REFERENCES `organizations` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- End of schema dump
