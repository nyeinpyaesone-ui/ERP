# Development Workflow Guide

## 1. Git Branching Strategy

### Branch Types
- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features (e.g., `feature/inventory-module`)
- `bugfix/*` - Bug fixes (e.g., `bugfix/login-error`)
- `hotfix/*` - Urgent production fixes
- `release/*` - Release preparation

### Branch Naming Convention
```
{type}/{ticket-id}-{short-description}
Example: feature/ERP-101-inventory-tracking
```

## 2. Development Process

### Step 1: Create Feature Branch
```bash
git checkout develop
git pull origin develop
git checkout -b feature/ERP-101-inventory-tracking
```

### Step 2: Make Changes
- Follow coding standards
- Write tests alongside code
- Commit frequently with clear messages

### Step 3: Commit Message Format
```
{type}: {subject}

{body}

{footer}
```

**Types**: feat, fix, docs, style, refactor, test, chore

**Example**:
```
feat: add inventory tracking module

- Implement Inventory model
- Add CRUD operations
- Create API endpoints

Closes #101
```

### Step 4: Push and Create PR
```bash
git push origin feature/ERP-101-inventory-tracking
```

## 3. Pre-Commit Checklist
- [ ] Code follows PEP 8
- [ ] All tests pass locally
- [ ] No linting errors
- [ ] Documentation updated
- [ ] Environment variables documented
- [ ] Database migrations created (if needed)

## 4. Local Testing Before Push
```bash
# Run all tests
pytest --cov=src

# Check linting
flake8 src/
black --check src/
isort --check-only src/

# Type checking
mypy src/

# Security check
bandit -r src/
```

## 5. Code Style Enforcement

### Install Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
```

### Pre-commit Configuration (.pre-commit-config.yaml)
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
```

## 6. Daily Workflow

### Morning Standup Prep
```bash
# Update local repo
git fetch origin
git status

# Check assigned tasks
# Review PRs needing attention
```

### End of Day
```bash
# Commit work in progress
git add .
git commit -m "wip: progress on feature"
git push

# Note: Use 'wip' prefix for incomplete work
```

## 7. Resolving Merge Conflicts
```bash
# Fetch latest changes
git fetch origin

# Rebase on develop
git rebase origin/develop

# Resolve conflicts, then:
git add <resolved-files>
git rebase --continue

# Force push if needed
git push --force-with-lease
```

## 8. Useful Git Commands

```bash
# View commit history
git log --oneline --graph --all

# Stash changes
git stash
git stash pop

# Undo last commit (keep changes)
git reset --soft HEAD~1

# View diff
git diff develop

# Clean untracked files
git clean -fdn  # Dry run first
```
