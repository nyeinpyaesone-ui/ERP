"""
Database Migrations Router
Handles schema migrations with rollback support
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
import subprocess
import os
from datetime import datetime

router = APIRouter(prefix="/api/v1/migrations", tags=["migrations"])

# In-memory migration history (use database in production)
migration_history = []


class MigrationInfo:
    def __init__(self, revision: str, message: str, status: str):
        self.revision = revision
        self.message = message
        self.status = status
        self.applied_at = datetime.utcnow()


def run_alembic_command(command: List[str]) -> dict:
    """Run alembic command and return result"""
    try:
        # In production, set proper env vars and path
        env = os.environ.copy()
        env['ALEMBIC_CONFIG'] = 'alembic.ini'
        
        result = subprocess.run(
            ['alembic'] + command,
            capture_output=True,
            text=True,
            env=env,
            cwd='/workspace/backend'
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@router.get("/status")
async def get_migration_status():
    """Get current migration status"""
    result = run_alembic_command(['current'])
    
    if result['success']:
        return {
            'current_revision': result['stdout'].strip(),
            'status': 'up_to_date' if result['stdout'].strip() else 'no_migrations',
            'message': 'Database is up to date' if result['stdout'].strip() else 'No migrations applied'
        }
    else:
        raise HTTPException(status_code=500, detail=result.get('error', 'Failed to get migration status'))


@router.get("/history")
async def get_migration_history(limit: Optional[int] = 50):
    """Get migration history"""
    result = run_alembic_command(['history'])
    
    if result['success']:
        lines = result['stdout'].strip().split('\n')
        migrations = []
        for line in lines[-limit:]:
            if line.strip():
                parts = line.split(' -> ')
                if len(parts) == 2:
                    migrations.append({
                        'revision': parts[1].split(' ')[0],
                        'previous': parts[0],
                        'message': parts[1].split(' ', 1)[1] if ' ' in parts[1] else ''
                    })
        return {'migrations': migrations, 'total': len(migrations)}
    else:
        raise HTTPException(status_code=500, detail=result.get('error', 'Failed to get migration history'))


@router.post("/upgrade")
async def upgrade_database(revision: str = "head"):
    """Upgrade database to specified revision"""
    result = run_alembic_command(['upgrade', revision])
    
    if result['success']:
        migration_info = MigrationInfo(revision, f"Upgrade to {revision}", "completed")
        migration_history.append(migration_info)
        
        return {
            'status': 'success',
            'message': f'Database upgraded to {revision}',
            'output': result['stdout']
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {result.get('stderr', result.get('error', 'Unknown error'))}"
        )


@router.post("/downgrade")
async def downgrade_database(revision: str = "-1"):
    """Downgrade database by one or to specific revision"""
    result = run_alembic_command(['downgrade', revision])
    
    if result['success']:
        return {
            'status': 'success',
            'message': f'Database downgraded to {revision}',
            'output': result['stdout']
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Downgrade failed: {result.get('stderr', result.get('error', 'Unknown error'))}"
        )


@router.post("/generate")
async def generate_migration(message: str):
    """Generate new migration file"""
    sanitized_message = message.replace(' ', '_')
    result = run_alembic_command(['revision', '--autogenerate', '-m', message])
    
    if result['success']:
        return {
            'status': 'success',
            'message': f'Migration generated: {sanitized_message}',
            'output': result['stdout']
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Generation failed: {result.get('stderr', result.get('error', 'Unknown error'))}"
        )


@router.get("/pending")
async def get_pending_migrations():
    """Get list of pending migrations"""
    result = run_alembic_command(['heads'])
    
    if result['success']:
        heads = [line.strip() for line in result['stdout'].strip().split('\n') if line.strip()]
        return {
            'pending_migrations': heads,
            'count': len(heads)
        }
    else:
        raise HTTPException(status_code=500, detail=result.get('error', 'Failed to get pending migrations'))
