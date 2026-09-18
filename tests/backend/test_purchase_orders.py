"""
Test suite for Purchase Order module
Tests security, tenancy, and transactional integrity
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.models import PurchaseOrder, PurchaseOrderItem, POApproval, Tenant, Vendor, User
from app.services.transaction_service import TransactionService, CompensationTransaction
from app.routers.purchase_orders import (
    generate_po_number,
    get_approval_level,
    check_segregation_of_duties
)


class TestTenancyModels:
    """Test tenant isolation models"""
    
    def test_tenant_creation(self):
        """Test tenant model can be instantiated"""
        from datetime import date
        tenant = Tenant(
            name="Test Company",
            subdomain="testcompany",
            schema_name="tenant_testcompany",
            plan="professional",
            max_users=50,
            max_storage_gb=100,
            subscription_start=date(2024, 1, 1),
            subscription_end=date(2025, 1, 1),
            is_active=True
        )
        
        assert tenant.name == "Test Company"
        assert tenant.subdomain == "testcompany"
        assert tenant.is_active is True
        assert tenant.plan == "professional"
    
    def test_tenant_relationships(self):
        """Test tenant has proper relationships"""
        tenant = Tenant(
            name="Test Company",
            subdomain="testcompany",
            schema_name="tenant_testcompany"
        )
        
        # Verify relationship is configured
        assert hasattr(tenant, 'users')


class TestPurchaseOrderSecurity:
    """Test PO security controls"""
    
    @pytest.mark.asyncio
    async def test_segregation_of_duties(self):
        """Test that requester cannot approve their own PO"""
        db = AsyncMock(spec=AsyncSession)
        
        # Requester trying to approve their own PO should fail
        result = await check_segregation_of_duties(db, requester_id=1, approver_id=1)
        assert result is False
        
        # Different approver should pass
        result = await check_segregation_of_duties(db, requester_id=1, approver_id=2)
        assert result is True
    
    def test_approval_levels(self):
        """Test approval level thresholds"""
        assert get_approval_level(500) == 1  # Manager
        assert get_approval_level(5000) == 2  # Director
        assert get_approval_level(50000) == 3  # Executive
    
    @pytest.mark.asyncio
    async def test_po_number_generation(self):
        """Test unique PO number generation"""
        db = AsyncMock(spec=AsyncSession)
        
        # Mock the database response
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)
        
        po_number = await generate_po_number(db)
        
        assert po_number.startswith("PO-")
        assert len(po_number.split("-")) == 3


class TestTransactionalIntegrity:
    """Test transaction management"""
    
    @pytest.mark.asyncio
    async def test_transaction_context_manager_success(self):
        """Test successful transaction commits"""
        db = AsyncMock(spec=AsyncSession)
        db.begin = MagicMock()
        
        async def mock_begin():
            yield db
        
        db.begin.return_value.__aenter__ = AsyncMock(return_value=db)
        db.begin.return_value.__aexit__ = AsyncMock(return_value=None)
        
        async with TransactionService.transaction(db) as session:
            assert session == db
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self):
        """Test transaction rolls back on error"""
        db = AsyncMock(spec=AsyncSession)
        db.rollback = AsyncMock()
        
        async def mock_begin():
            raise Exception("Test error")
            yield db
        
        db.begin.return_value.__aenter__ = AsyncMock(side_effect=Exception("Test error"))
        db.begin.return_value.__aexit__ = AsyncMock(return_value=None)
        
        try:
            async with TransactionService.transaction(db):
                pass
        except Exception:
            pass
        
        db.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transaction_log_creation(self):
        """Test transaction logging"""
        db = AsyncMock(spec=AsyncSession)
        db.flush = AsyncMock()
        db.add = MagicMock()
        
        transaction_id = await TransactionService.log_transaction(
            db=db,
            entity_type="purchase_order",
            entity_id=1,
            action="create",
            user_id=1,
            tenant_id=1
        )
        
        assert transaction_id is not None
        assert "purchase_order_1_" in transaction_id
        db.add.assert_called_once()


class TestCompensationPattern:
    """Test distributed transaction compensation"""
    
    @pytest.mark.asyncio
    async def test_compensation_execution(self):
        """Test compensations execute in reverse order"""
        db = AsyncMock(spec=AsyncSession)
        comp_txn = CompensationTransaction(db)
        
        executed = []
        
        async def op1():
            executed.append("op1")
        
        async def comp1():
            executed.append("comp1")
        
        async def op2():
            executed.append("op2")
        
        async def comp2():
            executed.append("comp2")
        
        await comp_txn.add_operation(op1, comp1)
        await comp_txn.add_operation(op2, comp2)
        await comp_txn.rollback()
        
        # Compensations should execute in reverse order
        assert executed == ["op1", "op2", "comp2", "comp1"]
    
    @pytest.mark.asyncio
    async def test_compensation_error_handling(self):
        """Test compensation continues on error"""
        db = AsyncMock(spec=AsyncSession)
        comp_txn = CompensationTransaction(db)
        
        async def failing_comp():
            raise Exception("Compensation failed")
        
        comp_txn.compensations.append(failing_comp)
        
        # Should not raise, but log error
        with patch.object(comp_txn.logger, 'error') as mock_log:
            await comp_txn.rollback()
            mock_log.assert_called_once()


class TestTenantIsolation:
    """Test tenant isolation in queries"""
    
    def test_po_has_tenant_id(self):
        """Test PO model includes tenant_id"""
        po = PurchaseOrder(
            tenant_id=1,
            po_number="PO-TEST-001",
            vendor_id=1,
            requester_id=1,
            total_amount=1000
        )
        
        assert po.tenant_id == 1
    
    def test_vendor_has_tenant_id(self):
        """Test Vendor model includes tenant_id"""
        vendor = Vendor(
            tenant_id=1,
            name="Test Vendor"
        )
        
        assert vendor.tenant_id == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
