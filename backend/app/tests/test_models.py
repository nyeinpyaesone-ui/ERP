"""
Unit tests for models module.
"""
import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import (
    User, Company, Contact, Deal, Department, Employee,
    Product, InventoryMovement, Invoice, InvoiceItem, Payment,
    Project, Task, Document
)


@pytest.fixture
def test_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_session(test_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestUser:
    """Test User model."""

    def test_create_user(self, test_session):
        """Test creating a user."""
        user = User(
            email="test@example.com",
            hashed_password="hashed123",
            full_name="Test User"
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.role == "user"  # default
        assert user.is_active is True  # default

    def test_user_default_role(self, test_session):
        """Test user default role is 'user'."""
        user = User(
            email="test2@example.com",
            hashed_password="hash",
            full_name="Test"
        )
        test_session.add(user)
        test_session.commit()
        
        assert user.role == "user"

    def test_user_relationships(self, test_session):
        """Test user relationships are defined."""
        user = User(
            email="test3@example.com",
            hashed_password="hash",
            full_name="Test"
        )
        test_session.add(user)
        test_session.commit()
        
        assert hasattr(user, 'contacts')
        assert hasattr(user, 'deals')
        assert hasattr(user, 'projects_managed')
        assert hasattr(user, 'tasks')


class TestCompany:
    """Test Company model."""

    def test_create_company(self, test_session):
        """Test creating a company."""
        company = Company(
            name="Test Corp",
            industry="Technology"
        )
        test_session.add(company)
        test_session.commit()
        test_session.refresh(company)
        
        assert company.id is not None
        assert company.name == "Test Corp"
        assert company.industry == "Technology"

    def test_company_has_contacts_relationship(self, test_session):
        """Test company has contacts relationship."""
        company = Company(name="Test Corp")
        test_session.add(company)
        test_session.commit()
        
        assert hasattr(company, 'contacts')
        assert hasattr(company, 'deals')
        assert hasattr(company, 'invoices')


class TestContact:
    """Test Contact model."""

    def test_create_contact(self, test_session):
        """Test creating a contact."""
        contact = Contact(
            first_name="John",
            last_name="Doe",
            email="john@example.com"
        )
        test_session.add(contact)
        test_session.commit()
        test_session.refresh(contact)
        
        assert contact.id is not None
        assert contact.first_name == "John"
        assert contact.last_name == "Doe"
        assert contact.status == "lead"  # default

    def test_contact_lifetime_value_default(self, test_session):
        """Test contact lifetime value defaults to 0."""
        contact = Contact(
            first_name="Jane",
            last_name="Doe"
        )
        test_session.add(contact)
        test_session.commit()
        
        assert float(contact.lifetime_value) == 0.0


class TestProduct:
    """Test Product model."""

    def test_create_product(self, test_session):
        """Test creating a product."""
        product = Product(
            sku="PROD-001",
            name="Test Product",
            unit_price=99.99
        )
        test_session.add(product)
        test_session.commit()
        test_session.refresh(product)
        
        assert product.id is not None
        assert product.sku == "PROD-001"
        assert product.name == "Test Product"
        assert float(product.unit_price) == 99.99
        assert product.quantity_in_stock == 0  # default

    def test_product_reorder_defaults(self, test_session):
        """Test product reorder level and quantity defaults."""
        product = Product(
            sku="PROD-002",
            name="Test Product 2"
        )
        test_session.add(product)
        test_session.commit()
        
        assert product.reorder_level == 10
        assert product.reorder_quantity == 50
        assert product.status == "active"


class TestInvoice:
    """Test Invoice model."""

    def test_create_invoice(self, test_session):
        """Test creating an invoice."""
        invoice = Invoice(
            invoice_number="INV-001",
            issue_date=date.today(),
            due_date=date.today(),
            subtotal=1000.00,
            tax_rate=10.00,
            tax_amount=100.00,
            total=1100.00
        )
        test_session.add(invoice)
        test_session.commit()
        test_session.refresh(invoice)
        
        assert invoice.id is not None
        assert invoice.invoice_number == "INV-001"
        assert invoice.status == "draft"  # default
        assert invoice.amount_paid == 0  # default

    def test_invoice_has_items_relationship(self, test_session):
        """Test invoice has items relationship."""
        invoice = Invoice(
            invoice_number="INV-002",
            issue_date=date.today(),
            due_date=date.today()
        )
        test_session.add(invoice)
        test_session.commit()
        
        assert hasattr(invoice, 'items')
        assert hasattr(invoice, 'payments')


class TestProject:
    """Test Project model."""

    def test_create_project(self, test_session):
        """Test creating a project."""
        project = Project(
            name="Test Project",
            description="A test project"
        )
        test_session.add(project)
        test_session.commit()
        test_session.refresh(project)
        
        assert project.id is not None
        assert project.name == "Test Project"
        assert project.status == "planning"  # default
        assert project.priority == "medium"  # default
        assert project.progress == 0  # default

    def test_project_has_tasks_relationship(self, test_session):
        """Test project has tasks relationship."""
        project = Project(name="Test Project")
        test_session.add(project)
        test_session.commit()
        
        assert hasattr(project, 'tasks')


class TestTask:
    """Test Task model."""

    def test_create_task(self, test_session):
        """Test creating a task."""
        project = Project(name="Parent Project")
        test_session.add(project)
        test_session.commit()
        
        task = Task(
            project_id=project.id,
            title="Test Task"
        )
        test_session.add(task)
        test_session.commit()
        test_session.refresh(task)
        
        assert task.id is not None
        assert task.title == "Test Task"
        assert task.status == "todo"  # default
        assert task.priority == "medium"  # default

    def test_task_subtask_relationship(self, test_session):
        """Test task subtask relationship."""
        project = Project(name="Parent Project")
        test_session.add(project)
        test_session.commit()
        
        parent_task = Task(
            project_id=project.id,
            title="Parent Task"
        )
        test_session.add(parent_task)
        test_session.commit()
        
        child_task = Task(
            project_id=project.id,
            title="Child Task",
            parent_task_id=parent_task.id
        )
        test_session.add(child_task)
        test_session.commit()
        
        assert hasattr(parent_task, 'subtasks')
