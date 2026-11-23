"""
Unit Tests for Inventory Models
================================
Tests for Warehouse, Category, Product, StockLevel, and StockMovement models.
"""
import pytest
from django.db import IntegrityError
from src.modules.inventory.models import (
    Warehouse, Category, Product, StockLevel, StockMovement
)


@pytest.mark.unit
class TestWarehouseModel:
    """Test cases for Warehouse model."""
    
    @pytest.fixture
    def warehouse(self, db):
        return Warehouse.objects.create(
            name="Main Warehouse",
            code="WH001",
            address="123 Storage St"
        )
    
    def test_create_warehouse(self, warehouse):
        assert warehouse.name == "Main Warehouse"
        assert warehouse.code == "WH001"
        assert warehouse.is_active is True
    
    def test_warehouse_str_representation(self, warehouse):
        assert str(warehouse) == "WH001 - Main Warehouse"
    
    def test_warehouse_unique_code(self, db):
        Warehouse.objects.create(name="Warehouse 1", code="WH002")
        with pytest.raises(IntegrityError):
            Warehouse.objects.create(name="Warehouse 2", code="WH002")
    
    def test_warehouse_ordering(self, db):
        wh1 = Warehouse.objects.create(name="Z Warehouse", code="WH003")
        wh2 = Warehouse.objects.create(name="A Warehouse", code="WH004")
        
        warehouses = list(Warehouse.objects.all())
        assert warehouses[0] == wh2
        assert warehouses[1] == wh1


@pytest.mark.unit
class TestCategoryModel:
    """Test cases for Category model."""
    
    @pytest.fixture
    def category(self, db):
        return Category.objects.create(
            name="Electronics",
            description="Electronic devices and accessories"
        )
    
    def test_create_category(self, category):
        assert category.name == "Electronics"
        assert category.parent is None
    
    def test_category_str_representation(self, category):
        assert str(category) == "Electronics"
    
    def test_nested_categories(self, db, category):
        child = Category.objects.create(
            name="Smartphones",
            parent=category
        )
        
        assert child.parent == category
        assert category.children.count() == 1


@pytest.mark.unit
class TestProductModel:
    """Test cases for Product model."""
    
    @pytest.fixture
    def category(self, db):
        return Category.objects.create(name="Test Category")
    
    @pytest.fixture
    def product(self, db, category):
        return Product.objects.create(
            sku="PROD001",
            name="Test Product",
            category=category,
            unit_price=99.99,
            cost_price=50.00,
            reorder_level=10
        )
    
    def test_create_product(self, product):
        assert product.sku == "PROD001"
        assert product.unit_price == 99.99
        assert product.is_active is True
    
    def test_product_str_representation(self, product):
        assert str(product) == "PROD001 - Test Product"
    
    def test_product_unique_sku(self, db, category):
        Product.objects.create(
            sku="PROD002",
            name="Another Product",
            category=category,
            unit_price=49.99
        )
        with pytest.raises(IntegrityError):
            Product.objects.create(
                sku="PROD002",
                name="Duplicate SKU",
                category=category,
                unit_price=29.99
            )
    
    def test_product_total_stock_empty(self, db, product):
        assert product.total_stock == 0
    
    def test_product_total_stock_with_levels(self, db, product):
        warehouse1 = Warehouse.objects.create(name="WH1", code="WH1")
        warehouse2 = Warehouse.objects.create(name="WH2", code="WH2")
        
        StockLevel.objects.create(product=product, warehouse=warehouse1, quantity=50)
        StockLevel.objects.create(product=product, warehouse=warehouse2, quantity=30)
        
        assert product.total_stock == 80


@pytest.mark.unit
class TestStockLevelModel:
    """Test cases for StockLevel model."""
    
    @pytest.fixture
    def setup_stock(self, db):
        warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        category = Category.objects.create(name="Test Cat")
        product = Product.objects.create(
            sku="TEST001",
            name="Test Item",
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
    
    def test_create_stock_level(self, setup_stock):
        stock = setup_stock['stock']
        assert stock.quantity == 100
        assert stock.reserved_quantity == 20
    
    def test_available_quantity(self, setup_stock):
        assert setup_stock['stock'].available_quantity == 80
    
    def test_stock_level_unique_constraint(self, db, setup_stock):
        with pytest.raises(IntegrityError):
            StockLevel.objects.create(
                product=setup_stock['product'],
                warehouse=setup_stock['warehouse'],
                quantity=50
            )
    
    def test_stock_level_str_representation(self, setup_stock):
        stock = setup_stock['stock']
        expected = f"{stock.product.sku} @ {stock.warehouse.code}: {stock.quantity}"
        assert str(stock) == expected


@pytest.mark.unit
class TestStockMovementModel:
    """Test cases for StockMovement model."""
    
    @pytest.fixture
    def setup_movement(self, db):
        warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        category = Category.objects.create(name="Test Cat")
        product = Product.objects.create(
            sku="MOVE001",
            name="Move Item",
            category=category,
            unit_price=15.00
        )
        return {'product': product, 'warehouse': warehouse}
    
    def test_stock_in_movement(self, db, setup_movement):
        movement = StockMovement.objects.create(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse'],
            movement_type='IN',
            quantity=50,
            performed_by="user1"
        )
        
        assert movement.movement_type == 'IN'
        assert movement.quantity == 50
        
        # Verify stock level was updated
        stock_level = StockLevel.objects.get(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse']
        )
        assert stock_level.quantity == 50
    
    def test_stock_out_movement(self, db, setup_movement):
        # First add stock
        StockLevel.objects.create(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse'],
            quantity=100
        )
        
        movement = StockMovement.objects.create(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse'],
            movement_type='OUT',
            quantity=-30,
            performed_by="user2"
        )
        
        stock_level = StockLevel.objects.get(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse']
        )
        assert stock_level.quantity == 70
    
    def test_adjustment_movement(self, db, setup_movement):
        StockLevel.objects.create(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse'],
            quantity=100
        )
        
        movement = StockMovement.objects.create(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse'],
            movement_type='ADJUSTMENT',
            quantity=85,  # Set to exact value
            performed_by="admin"
        )
        
        stock_level = StockLevel.objects.get(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse']
        )
        assert stock_level.quantity == 85
    
    def test_movement_str_representation(self, db, setup_movement):
        movement = StockMovement.objects.create(
            product=setup_movement['product'],
            warehouse=setup_movement['warehouse'],
            movement_type='IN',
            quantity=25,
            performed_by="user1"
        )
        
        expected = f"IN: {movement.product.sku} ({movement.quantity})"
        assert str(movement) == expected
