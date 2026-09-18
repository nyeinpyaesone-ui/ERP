from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, OperationalError
import logging
import uuid
from datetime import datetime
from app.models import TransactionLog

logger = logging.getLogger(__name__)


class TransactionService:
    """Manage database transactions with proper error handling and audit logging"""
    
    @staticmethod
    @asynccontextmanager
    async def transaction(db: AsyncSession):
        """Context manager for database transactions with automatic rollback on error"""
        try:
            async with db.begin():
                yield db
        except SQLAlchemyError as e:
            logger.error(f"Transaction failed: {str(e)}")
            await db.rollback()
            raise
        except Exception as e:
            logger.error(f"Unexpected error in transaction: {str(e)}")
            await db.rollback()
            raise
    
    @staticmethod
    async def execute_atomic(db: AsyncSession, operations: list):
        """Execute multiple operations atomically"""
        async with db.begin():
            try:
                results = []
                for op in operations:
                    result = await op(db)
                    results.append(result)
                return results
            except Exception as e:
                await db.rollback()
                logger.error(f"Atomic operation failed: {str(e)}")
                raise
    
    @staticmethod
    async def retry_on_deadlock(db: AsyncSession, func, max_retries: int = 3):
        """Retry operation on deadlock detection"""
        for attempt in range(max_retries):
            try:
                async with db.begin():
                    return await func(db)
            except OperationalError as e:
                if "deadlock" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"Deadlock detected, retrying... ({attempt + 1}/{max_retries})")
                    await db.rollback()
                    continue
                raise
    
    @staticmethod
    async def log_transaction(
        db: AsyncSession,
        entity_type: str,
        entity_id: int,
        action: str,
        old_values: dict = None,
        new_values: dict = None,
        user_id: int = None,
        tenant_id: int = None,
        status: str = "completed",
        error_message: str = None
    ):
        """Log a transaction for audit purposes"""
        transaction_id = f"{entity_type}_{entity_id}_{datetime.utcnow().isoformat()}_{uuid.uuid4().hex[:8]}"
        
        log_entry = TransactionLog(
            transaction_id=transaction_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            user_id=user_id,
            tenant_id=tenant_id,
            status=status,
            error_message=error_message
        )
        
        db.add(log_entry)
        await db.flush()
        
        return transaction_id


class CompensationTransaction:
    """Handle distributed transactions with compensation pattern"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.compensations = []
        self.logger = logging.getLogger(__name__)
    
    async def add_operation(self, operation, compensation):
        """Add operation and its compensation function"""
        try:
            await operation()
            self.compensations.append(compensation)
        except Exception as e:
            await self.rollback()
            raise
    
    async def rollback(self):
        """Execute compensations in reverse order"""
        for compensation in reversed(self.compensations):
            try:
                await compensation()
            except Exception as e:
                self.logger.error(f"Compensation failed: {str(e)}")
                # Continue with other compensations - don't raise
                # Alert admins - manual intervention may be needed
                pass
