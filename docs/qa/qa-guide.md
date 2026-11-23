# Quality Assurance Guide

## 1. Testing Strategy

### Testing Pyramid
```
        /\
       /  \      E2E Tests (10%)
      /----\    
     /      \   Integration Tests (20%)
    /--------\  
   /          \ Unit Tests (70%)
  /------------\
```

## 2. Test Types

### Unit Tests
- Test individual functions/classes
- Fast execution (< 100ms per test)
- No external dependencies
- Location: `tests/unit/`

### Integration Tests
- Test component interactions
- Database/API interactions
- Location: `tests/integration/`

### End-to-End (E2E) Tests
- Full user workflows
- Browser automation (Selenium/Playwright)
- Location: `tests/e2e/`

## 3. Writing Tests

### Unit Test Example
```python
# tests/unit/test_inventory.py
import pytest
from src.inventory.models import Product

@pytest.mark.django_db
def test_product_creation():
    product = Product.objects.create(
        name="Test Product",
        sku="TEST-001",
        price=99.99
    )
    assert product.name == "Test Product"
    assert product.sku == "TEST-001"
    assert product.price == 99.99
```

### Integration Test Example
```python
# tests/integration/test_api.py
import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
def test_inventory_api():
    client = APIClient()
    response = client.get('/api/inventory/products/')
    assert response.status_code == 200
    assert 'results' in response.data
```

## 4. Running Tests

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Run Specific Test File
```bash
pytest tests/unit/test_inventory.py
```

### Run Specific Test Function
```bash
pytest tests/unit/test_inventory.py::test_product_creation
```

### Run Tests Matching Pattern
```bash
pytest -k "inventory"
```

## 5. Test Configuration (pytest.ini)
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.test
python_files = tests.py test_*.py *_tests.py
addopts = 
    -v
    --strict-markers
    --tb=short
    --cov=src
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    e2e: marks tests as end-to-end tests
```

## 6. Test Data Management

### Fixtures
```python
# tests/conftest.py
import pytest
from src.inventory.models import Product, Category

@pytest.fixture
def sample_category():
    return Category.objects.create(name="Electronics")

@pytest.fixture
def sample_product(sample_category):
    return Product.objects.create(
        name="Laptop",
        sku="ELEC-001",
        price=999.99,
        category=sample_category
    )

@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()
```

### Factory Boy (Advanced)
```python
# tests/factories.py
import factory
from src.inventory.models import Product

class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product
    
    name = factory.Sequence(lambda n: f"Product {n}")
    sku = factory.Sequence(lambda n: f"SKU-{n:04d}")
    price = factory.Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
```

## 7. QA Checklist

### Before Merge
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Code coverage ≥ 80%
- [ ] No linting errors
- [ ] Security scans pass
- [ ] Performance benchmarks met

### Pre-Release
- [ ] E2E tests pass
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Documentation reviewed
- [ ] UAT sign-off received

## 8. Continuous Testing

### Local Pre-Push
```bash
#!/bin/bash
# scripts/pre-push-tests.sh

echo "Running tests..."
pytest --cov=src --cov-fail-under=80

echo "Checking linting..."
flake8 src/
black --check src/

echo "Running security scan..."
bandit -r src/

echo "All checks passed!"
```

### Test Reports
```bash
# Generate HTML report
pytest --cov=src --cov-report=html

# Generate XML for CI
pytest --cov=src --cov-report=xml

# Generate JUnit XML
pytest --junitxml=test-results.xml
```

## 9. Performance Testing

### Load Testing with Locust
```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between

class InventoryUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def view_products(self):
        self.client.get("/api/inventory/products/")
    
    @task(3)
    def search_products(self):
        self.client.get("/api/inventory/products/search?q=laptop")
```

### Run Load Test
```bash
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

## 10. Common Issues & Solutions

### Database Test Isolation
```python
@pytest.fixture
def db():
    # Django automatically handles DB rollback
    pass
```

### Mocking External Services
```python
from unittest.mock import patch

@patch('src.inventory.services.external_api_call')
def test_with_mock(mock_api):
    mock_api.return_value = {'status': 'success'}
    # Test code here
```

### Async Testing
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```
