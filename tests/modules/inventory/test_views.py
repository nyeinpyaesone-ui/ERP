"""
Unit Tests for Inventory Views
================================
Tests for all inventory API viewsets.
"""
import pytest
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework import status

from src.modules.inventory.models import Warehouse, Category, Product, StockLevel, StockMovement
from src.modules.inventory.views import (
    WarehouseViewSet,
    CategoryViewSet,
    ProductViewSet,
    StockLevelViewSet,
    StockMovementViewSet,
)


@pytest.mark.unit
class TestWarehouseViewSet:
    """Test cases for WarehouseViewSet."""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    @pytest.fixture
    def warehouses(self, db):
        return [
            Warehouse.objects.create(name="WH1", code="WH001"),
            Warehouse.objects.create(name="WH2", code="WH002"),
        ]
    
    def test_list_warehouses(self, db, api_client, warehouses):
        response = api_client.get('/api/warehouses/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
    
    def test_create_warehouse(self, db, api_client):
        data = {
            'name': 'New Warehouse',
            'code': 'NWH001',
            'address': '123 New St'
        }
        response = api_client.post('/api/warehouses/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Warehouse.objects.filter(code='NWH001').exists()
    
    def test_retrieve_warehouse(self, db, api_client, warehouses):
        warehouse = warehouses[0]
        response = api_client.get(f'/api/warehouses/{warehouse.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['code'] == 'WH001'
    
    def test_update_warehouse(self, db, api_client, warehouses):
        warehouse = warehouses[0]
        data = {'name': 'Updated Name'}
        response = api_client.patch(f'/api/warehouses/{warehouse.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        warehouse.refresh_from_db()
        assert warehouse.name == 'Updated Name'
    
    def test_delete_warehouse(self, db, api_client, warehouses):
        warehouse = warehouses[0]
        response = api_client.delete(f'/api/warehouses/{warehouse.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Warehouse.objects.filter(id=warehouse.id).exists()


@pytest.mark.unit
class TestProductViewSet:
    """Test cases for ProductViewSet."""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    @pytest.fixture
    def category(self, db):
        return Category.objects.create(name="Test Category")
    
    @pytest.fixture
    def products(self, db, category):
        return [
            Product.objects.create(
                sku="PRD001",
                name="Product 1",
                category=category,
                unit_price=99.99
            ),
            Product.objects.create(
                sku="PRD002",
                name="Product 2",
                category=category,
                unit_price=49.99
            ),
        ]
    
    def test_list_products(self, db, api_client, products):
        response = api_client.get('/api/products/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
    
    def test_create_product(self, db, api_client, category):
        data = {
            'sku': 'NEW001',
            'name': 'New Product',
            'category': category.id,
            'unit_price': 29.99
        }
        response = api_client.post('/api/products/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Product.objects.filter(sku='NEW001').exists()
    
    def test_search_products(self, db, api_client, products):
        response = api_client.get('/api/products/?search=Product+1')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['sku'] == 'PRD001'
    
    def test_stock_summary_action(self, db, api_client, products):
        product = products[0]
        warehouse = Warehouse.objects.create(name="WH1", code="WH1")
        StockLevel.objects.create(product=product, warehouse=warehouse, quantity=50)
        
        response = api_client.get(f'/api/products/{product.id}/stock_summary/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_stock'] == 50
        assert 'warehouses' in response.data


@pytest.mark.unit
class TestStockLevelViewSet:
    """Test cases for StockLevelViewSet."""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    @pytest.fixture
    def setup_stock(self, db):
        warehouse = Warehouse.objects.create(name="Test WH", code="TWH")
        category = Category.objects.create(name="Test Cat")
        product = Product.objects.create(
            sku="STK001",
            name="Stock Item",
            category=category,
            unit_price=10.00,
            reorder_level=20
        )
        stock = StockLevel.objects.create(
            product=product,
            warehouse=warehouse,
            quantity=100,
            reserved_quantity=20
        )
        return {'stock': stock, 'product': product, 'warehouse': warehouse}
    
    def test_list_stock_levels(self, db, api_client, setup_stock):
        response = api_client.get('/api/stock-levels/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
    
    def test_low_stock_action(self, db, api_client, setup_stock):
        # Create a low stock item
        category = Category.objects.create(name="Cat2")
        product = Product.objects.create(
            sku="LOW001",
            name="Low Stock Item",
            category=category,
            unit_price=5.00,
            reorder_level=50
        )
        warehouse = Warehouse.objects.get(code="TWH")
        StockLevel.objects.create(
            product=product,
            warehouse=warehouse,
            quantity=10  # Below reorder level
        )
        
        response = api_client.get('/api/stock-levels/low_stock/')
        assert response.status_code == status.HTTP_200_OK
        # Should include our low stock item
        assert any(item['product_sku'] == 'LOW001' for item in response.data)


@pytest.mark.unit
class TestStockMovementViewSet:
    """Test cases for StockMovementViewSet."""
    
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
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
            performed_by="testuser"
        )
        return {'movement': movement, 'product': product, 'warehouse': warehouse}
    
    def test_list_movements(self, db, api_client, setup_movement):
        response = api_client.get('/api/stock-movements/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
    
    def test_filter_movements_by_type(self, db, api_client, setup_movement):
        response = api_client.get('/api/stock-movements/?movement_type=IN')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1
    
    def test_adjust_stock_action(self, db, api_client, setup_movement):
        data = {
            'product_id': setup_movement['product'].id,
            'warehouse_id': setup_movement['warehouse'].id,
            'movement_type': 'IN',
            'quantity': 100,
            'reference': 'ADJ001',
            'notes': 'Test adjustment'
        }
        response = api_client.post('/api/stock-movements/adjust_stock/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['quantity'] == 100
        assert response.data['reference'] == 'ADJ001'
