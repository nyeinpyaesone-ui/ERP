# Contributing to ERP System

Thank you for your interest in contributing to the ERP System project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Communication](#communication)

## Code of Conduct

Please be respectful and constructive in all interactions. We are committed to providing a welcoming environment for all contributors.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/erp-project.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate the environment: `source venv/bin/activate`
5. Install dependencies: `pip install -r requirements.txt`
6. Install pre-commit hooks: `pre-commit install`

## Development Workflow

### Branch Naming Convention

- Feature branches: `feature/description-of-feature`
- Bug fixes: `fix/description-of-fix`
- Hotfixes: `hotfix/description-of-hotfix`
- Documentation: `docs/description-of-docs`

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
feat: add inventory tracking module
fix: resolve calculation error in finance reports
docs: update API documentation
test: add unit tests for user authentication
refactor: improve code structure in sales module
```

## Coding Standards

### Python Style Guide

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use Black for code formatting
- Use isort for import sorting
- Maximum line length: 100 characters
- Use type hints where possible

### Running Linters

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Run flake8
flake8 src/ tests/

# Run type checking
mypy src/
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_core.py

# Run tests by marker
pytest -m unit
pytest -m integration
```

### Writing Tests

- Write tests for all new features
- Aim for at least 80% code coverage
- Use descriptive test names
- Follow the Arrange-Act-Assert pattern
- Mock external dependencies

Example:

```python
def test_user_creation():
    """Test that a user can be created successfully."""
    # Arrange
    username = "testuser"
    email = "test@example.com"
    
    # Act
    user = User.objects.create_user(username=username, email=email)
    
    # Assert
    assert user.username == username
    assert user.email == email
    assert user.is_active is True
```

## Submitting Changes

1. **Create a Pull Request**
   - Use a clear and descriptive title
   - Reference any related issues
   - Provide a detailed description of changes

2. **PR Checklist**
   - [ ] Tests added/updated
   - [ ] Documentation updated
   - [ ] Code follows style guidelines
   - [ ] All tests pass
   - [ ] No linting errors

3. **Code Review**
   - Be open to feedback
   - Address review comments promptly
   - Request re-review after making changes

## Communication

- Use GitHub Issues for bug reports and feature requests
- Join our discussion forum for questions
- Tag maintainers for urgent issues

## Questions?

If you have any questions, feel free to open an issue or reach out to the maintainers.

Thank you for contributing! 🎉
