#!/usr/bin/env python3
"""
Configuration Management Script
Helper script to manage environment-specific configurations
"""

import os
import shutil
from pathlib import Path

def setup_environment(env_name: str):
    """Setup environment-specific configuration"""
    config_dir = Path("config")
    env_file = config_dir / f"env_{env_name}.txt"
    target_env = Path(".env")
    
    if not env_file.exists():
        print(f"❌ Environment file {env_file} not found!")
        print(f"Available environments: {list_available_environments()}")
        return False
    
    # Backup existing .env if it exists
    if target_env.exists():
        backup_file = Path(f".env.backup.{env_name}")
        shutil.copy2(target_env, backup_file)
        print(f"📁 Backed up existing .env to {backup_file}")
    
    # Copy environment-specific config to .env
    shutil.copy2(env_file, target_env)
    print(f"✅ Environment '{env_name}' configured successfully!")
    print(f"📄 Configuration copied from {env_file} to .env")
    
    return True

def list_available_environments():
    """List all available environment configurations"""
    config_dir = Path("config")
    env_files = list(config_dir.glob("env_*.txt"))
    environments = [f.stem.replace("env_", "") for f in env_files]
    return environments

def show_current_config():
    """Show current configuration summary"""
    try:
        from config.settings import settings
        
        print("🔧 Current Configuration Summary:")
        print("=" * 50)
        print(f"Environment: {settings.environment}")
        print(f"App Name: {settings.app.name}")
        print(f"Debug Mode: {settings.app.debug}")
        print(f"Database URL: {settings.get_database_url()[:50]}...")
        print(f"Redis Host: {settings.redis.host}:{settings.redis.port}")
        print(f"JWT Secret Length: {len(settings.jwt.secret_key)}")
        print(f"Log Level: {settings.logging.level}")
        print(f"Rate Limit Fail Open: {settings.rate_limit.fail_open}")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")

def main():
    """Main CLI interface"""
    import sys
    
    if len(sys.argv) < 2:
        print("🔧 Configuration Management Script")
        print("=" * 40)
        print("Usage:")
        print("  python config_manager.py <environment>")
        print("  python config_manager.py show")
        print("  python config_manager.py list")
        print("")
        print("Examples:")
        print("  python config_manager.py development")
        print("  python config_manager.py staging")
        print("  python config_manager.py production")
        print("  python config_manager.py show")
        print("  python config_manager.py list")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        environments = list_available_environments()
        print("📋 Available Environments:")
        for env in environments:
            print(f"  - {env}")
    
    elif command == "show":
        show_current_config()
    
    elif command in ["development", "staging", "production"]:
        setup_environment(command)
        print("\n🔄 Restart your application to apply the new configuration!")
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Available commands: development, staging, production, show, list")

if __name__ == "__main__":
    main()
