# Static Files Configuration

## Directory Structure

```
backend/static/
├── uploads/          # User uploaded files
├── documents/        # Document management files
├── images/           # General images
├── avatars/          # User profile avatars
├── reports/          # Generated reports (PDF, Excel)
└── temp/             # Temporary files
```

## API Endpoints

All static files are served through the following endpoints:

| Endpoint | Directory | Purpose |
|----------|-----------|---------|
| `/static` | `backend/static/` | Root static files (HTML enabled) |
| `/static/uploads` | `backend/static/uploads/` | User uploads |
| `/static/documents` | `backend/static/documents/` | Documents |
| `/static/images` | `backend/static/images/` | Images |
| `/static/avatars` | `backend/static/avatars/` | User avatars |
| `/static/reports` | `backend/static/reports/` | Generated reports |

## Usage Examples

### Upload a file
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@myfile.pdf" \
  -H "Authorization: Bearer <token>"
```

### Access a uploaded file
```bash
# Direct access via static endpoint
http://localhost:8000/static/uploads/myfile.pdf

# Or specific path
http://localhost:8000/static/documents/myfile.pdf
```

### Avatar access
```bash
http://localhost:8000/static/avatars/user_123.jpg
```

## Docker Volume Mounts

In production, ensure these directories are mounted as volumes:

```yaml
volumes:
  - ./backend/static/uploads:/app/static/uploads
  - ./backend/static/documents:/app/static/documents
  - ./backend/static/images:/app/static/images
  - ./backend/static/avatars:/app/static/avatars
  - ./backend/static/reports:/app/static/reports
```

## Security Notes

- All static endpoints require authentication for write operations
- Read access to sensitive directories (documents, reports) should be protected
- File type validation should be implemented in upload handlers
- Maximum file size is configured in `config.py` (default: 50MB)

## Configuration

In `backend/app/config.py`:
```python
UPLOAD_DIR: str = "./uploads"
MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
```

## Auto-Creation

The `main.py` automatically creates all required directories on startup:
```python
os.makedirs(os.path.join(STATIC_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "documents"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "images"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "avatars"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "reports"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "temp"), exist_ok=True)
```
