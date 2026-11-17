"""
Unit Tests for Inventory Serializers
=====================================
Tests for all inventory model serializers.
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from src.modules.inventory.models import Warehouse, Category, Product, StockLevel, StockMovement
from src.modules.inventory.serializers import (
    WarehouseSerializer,
    CategorySerializer,
    ProductSerializer,
    StockLevelSerializer,
    StockMovementSerializer,
    StockAdjustmentSerializer,
)


@pytest.mark.unit
class TestWarehouseSerializer:
    """Test cases for WarehouseSerializer."""
    
    @pytest.fixture
    def warehouse(self, db):
        return Warehouse.objects.create(
            name="Test Warehouse",
            code="TWH001",
            address="123 Test St"
        )
    
    def test_warehouse_serializer_fields(self, warehouse):
        serializer = WarehouseSerializer(warehouse)
        data = serializer.data
        
        assert 'id' in data
        assert 'name' in data
        assert 'code' in data
        assert 'address' in data
        assert 'is_active' in data
        assert data['name'] == "Test Warehouse"
        assert data['code'] == "TWH001"
    
    def test_warehouse_serializer_create(self, db):
        data = {
            'name': 'New Warehouse',
            'code': 'NWH001',
            'address': '456 New St'
        }
        serializer = WarehouseSerializer(data=data)
        assert serializer.is_valid()
        warehouse = serializer.save()
        assert warehouse.name == 'New Warehouse'


@pytest.mark.unit
class TestCategorySerializer:
    """Test cases for CategorySerializer."""
    
    @pytest.fixture
    def category(self, db):
        return Category.objects.create(
            name="Electronics",
            description="Electronic items"
        )
    
    def test_category_serializer_fields(self, category):
        serializer = CategorySerializer(category)
        data = serializer.data
        
        assert 'id' in data
        assert 'name' in data
        assert 'description' in data
        assert 'children_count' in data
        assert data['name'] == "Electronics"
    
    def test_category_serializer_with_children(self, db, category):
        child = Category.objects.create(
            name="Phones",
            parent=category
        )
        serializer = CategorySerializer(category)
        data = serializer.data
        assert data['children_count'] == 1


@pytest.mark.unit
class TestProductSerializer:
    """Test cases for ProductSerializer."""
    
    @pytest.fixture
    def category(self, db):
        return Category.objects.create(name="Test Category")
    
    @pytest.fixture
    def product(self, db, category):
        return Product.objects.create(
            sku="PRD001",
            name="Test Product",
            category=category,
            unit_price=99.99,
            cost_price=50.00
        )
    
    def test_product_serializer_fields(self, product):
        serializer = ProductSerializer(product)
        data = serializer.data
        
        assert 'id' in data
        assert 'sku' in data
        assert 'name' in data
        assert 'unit_price' in data
        assert 'total_stock' in data
        assert 'category_name' in data
        assert data['sku'] == "PRD001"
        assert data['name'] == "Test Product"
    
    def test_product_serializer_total_stock(self, db, product):
        warehouse = Warehouse.objects.create(name="WH1", code="WH1")
        StockLevel.objects.create(product=product, warehouse=warehouse, quantity=50)
        
        serializer = ProductSerializer(product)
        data = serializer.data
        assert data['total_stock'] == 50


@pytest.mark.unit
class TestStockLevelSerializer:
    """Test cases for StockLevelSerializer."""
    
    @pytest.fixture
    def setup_stock(self, db):
        warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        category = Category.objects.create(name="Test Cat")
        product = Product.objects.create(
            sku="STK001",
            name="Stock Item",
            category=category,
            unit_price=10.00
        )
        stock = StockLevel.objects.create(
            product=product,
            warehouse=warehouse,
            quantity=100,
            reserved_quantity=20
        )
        return {'stock': stock, 'product': product, 'warehouse': warehouse}
    
    def test_stock_level_serializer_fields(self, setup_stock):
        serializer = StockLevelSerializer(setup_stock['stock'])
        data = serializer.data
        
        assert 'id' in data
        assert 'product' in data
        assert 'warehouse' in data
        assert 'quantity' in data
        assert 'reserved_quantity' in data
        assert 'available_quantity' in data
        assert 'product_sku' in data
        assert 'warehouse_name' in data
    
    def test_stock_level_available_quantity(self, setup_stock):
        serializer = StockLevelSerializer(setup_stock['stock'])
        data = serializer.data
        assert data['available_quantity'] == 80


@pytest.mark.unit
class TestStockMovementSerializer:
    """Test cases for StockMovementSerializer."""
    
    @pytest.fixture
    def setup_movement(self, db):
        warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        category = Category.objects.create(name="Test Cat")
        product = Product.objects.create(
            sku="MOV001",
            name="Move Item",
            category=category,
            unit_price=15.00
        )
        movement = StockMovement.objects.create(
            product=product,
            warehouse=warehouse,
            movement_type='IN',
            quantity=50,
            reference="REF001",
            notes="Test movement",
            performed_by="testuser"
        )
        return {'movement': movement, 'product': product, 'warehouse': warehouse}
    
    def test_stock_movement_serializer_fields(self, setup_movement):
        serializer = StockMovementSerializer(setup_movement['movement'])
        data = serializer.data
        
        assert 'id' in data
        assert 'product' in data
        assert 'warehouse' in data
        assert 'movement_type' in data
        assert 'quantity' in data
        assert 'reference' in data
        assert 'notes' in data
        assert 'performed_by' in data
        assert 'product_sku' in data
        assert data['movement_type'] == 'IN'
        assert data['quantity'] == 50


@pytest.mark.unit
class TestStockAdjustmentSerializer:
    """Test cases for StockAdjustmentSerializer."""
    
    @pytest.fixture
    def setup_data(self, db):
        warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        category = Category.objects.create(name="Test Cat")
        product = Product.objects.create(
            sku="ADJ001",
            name="Adjust Item",
            category=category,
            unit_price=20.00
        )
        return {
            'product': product,
            'warehouse': warehouse,
            'product_id': product.id,
            'warehouse_id': warehouse.id
        }
    
    def test_adjustment_serializer_valid_in(self, db, setup_data):
        data = {
            'product_id': setup_data['product_id'],
            'warehouse_id': setup_data['warehouse_id'],
            'movement_type': 'IN',
            'quantity': 100,
            'reference': 'ADJ001',
            'notes': 'Stock in'
        }
        serializer = StockAdjustmentSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
    
    def test_adjustment_serializer_invalid_product(self, setup_data):
        data = {
            'product_id': 99999,
            'warehouse_id': setup_data['warehouse_id'],
            'movement_type': 'IN',
            'quantity': 100
        }
        serializer = StockAdjustmentSerializer(data=data)
        assert not serializer.is_valid()
        assert 'product_id' in serializer.errors
    
    def test_adjustment_serializer_invalid_warehouse(self, setup_data):
        data = {
            'product_id': setup_data['product_id'],
            'warehouse_id': 99999,
            'movement_type': 'IN',
            'quantity': 100
        }
        serializer = StockAdjustmentSerializer(data=data)
        assert not serializer.is_valid()
        assert 'warehouse_id' in serializer.errors
    
    def test_adjustment_serializer_insufficient_stock(self, db, setup_data):
        # Try to remove stock when none exists
        data = {
            'product_id': setup_data['product_id'],
            'warehouse_id': setup_data['warehouse_id'],
            'movement_type': 'OUT',
            'quantity': -50
        }
        serializer = StockAdjustmentSerializer(data=data)
        assert not serializer.is_valid()
        assert 'quantity' in serializer.errors
