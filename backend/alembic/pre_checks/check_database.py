#!/usr/bin/env python3
"""Pre-migration validation checks"""

import sys
import shutil
from sqlalchemy import text, create_engine
from app.config import settings


def check_disk_space(min_gb: float = 1.0) -> bool:
    """Ensure sufficient disk space for migration"""
    total, used, free = shutil.disk_usage("/")
    free_gb = free / (1024 ** 3)
    
    if free_gb < min_gb:
        print(f"ERROR: Insufficient disk space. Required: {min_gb}GB, Available: {free_gb:.2f}GB")
        return False
    
    print(f"✓ Disk space check passed: {free_gb:.2f}GB available")
    return True


def check_database_connections() -> bool:
    """Check database connection pool availability"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"))
            active_connections = result.scalar()
            
            result = conn.execute(text("SHOW max_connections"))
            max_connections = result.scalar()
            
            print(f"✓ Database connections: {active_connections}/{max_connections} active")
            
            if active_connections > int(max_connections) * 0.8:
                print("WARNING: High number of active connections")
            
            return True
    except Exception as e:
        print(f"ERROR: Failed to check database connections: {str(e)}")
        return False


def validate_schema() -> bool:
    """Validate current schema state before migration"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'alembic_version'
                )
            """))
            
            if not result.scalar():
                print("WARNING: Alembic version table not found")
                return False
            
            # Get current version
            result = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"))
            current_version = result.scalar()
            print(f"✓ Current schema version: {current_version}")
            
            return True
    except Exception as e:
        print(f"ERROR: Schema validation failed: {str(e)}")
        return False


def check_locks() -> bool:
    """Check for long-running locks that might block migration"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT count(*) 
                FROM pg_locks 
                WHERE mode IN ('AccessExclusiveLock', 'ShareRowExclusiveLock')
                AND granted = true
            """))
            
            exclusive_locks = result.scalar()
            
            if exclusive_locks > 0:
                print(f"WARNING: {exclusive_locks} exclusive locks detected")
                return False
            
            print("✓ No blocking locks detected")
            return True
    except Exception as e:
        print(f"ERROR: Lock check failed: {str(e)}")
        return False


def run_all_checks() -> bool:
    """Run all pre-migration checks"""
    print("=" * 50)
    print("Running Pre-Migration Checks")
    print("=" * 50)
    
    checks = [
        ("Disk Space", check_disk_space),
        ("Database Connections", check_database_connections),
        ("Schema Validation", validate_schema),
        ("Lock Detection", check_locks),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n[{name}]")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"ERROR: {name} check failed with exception: {str(e)}")
            results.append(False)
    
    print("\n" + "=" * 50)
    if all(results):
        print("✓ All pre-migration checks passed")
        return True
    else:
        print("✗ Some pre-migration checks failed")
        print("Please resolve issues before proceeding with migration")
        return False


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
