import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Document
from app.services.activity_log import log_activity
from app.services.permissions import require_permission

router = APIRouter()

UPLOAD_DIR = settings.UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_SIZE = settings.MAX_UPLOAD_SIZE
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

CHUNK_SIZE = 8192  # 8KB chunks for streaming


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    entity_type: str | None = None,
    entity_id: int | None = None,
    title: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("documents", "create")),
):
    """Save an upload in streaming chunks, commit its record, and return metadata without the file path.

    ``entity_type`` and ``entity_id`` optionally associate the document with a
    record. An empty title falls back to the original filename. Raise HTTP 400
    for a missing filename or disallowed declared MIME type, and HTTP 413
    above ``MAX_UPLOAD_SIZE`` bytes; equality is allowed. File I/O errors clean
    up the partial file; DB failures roll back and remove the saved file.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, detail=f"File type {file.content_type} not allowed"
        )

    file_ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    # Stream file to disk in chunks while counting total size
    total_size = 0
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max size: {MAX_UPLOAD_SIZE} bytes",
                    )
                buffer.write(chunk)
    except HTTPException:
        # Clean up partial file on size error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception:
        # Clean up partial file on any other error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    doc = Document(
        title=title or file.filename,
        filename=file.filename,
        file_path=file_path,
        file_size=total_size,
        mime_type=file.content_type,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=current_user.id,
    )
    db.add(doc)
    try:
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    log_activity(
        db,
        user_id=current_user.id,
        action="document_uploaded",
        entity_type="document",
        entity_id=doc.id,
    )
    # Don't return file_path - security issue
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "entity_type": doc.entity_type,
        "entity_id": doc.entity_id,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at,
    }


@router.get("/documents")
def list_documents(
    entity_type: str | None = None,
    entity_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("documents", "read")),
):
    """Return documents newest first after ``skip`` records, capping ``limit`` at 100.

    Truthy entity filters are matched exactly; a zero ``entity_id`` is ignored.
    """
    if limit > 100:
        limit = 100
    query = db.query(Document)
    if entity_type:
        query = query.filter(Document.entity_type == entity_type)
    if entity_id:
        query = query.filter(Document.entity_id == entity_id)
    return query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/documents/{doc_id}")
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("documents", "read")),
):
    """Return document metadata without its file path.

    Raise HTTP 404 if the document does not exist.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Don't return file_path
    return {
        "id": doc.id,
        "title": doc.title,
        "filename": doc.filename,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "entity_type": doc.entity_type,
        "entity_id": doc.entity_id,
        "uploaded_by": doc.uploaded_by,
        "created_at": doc.created_at,
    }


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("documents", "delete")),
):
    """Remove the stored file if present, commit deletion, and return confirmation.

    Raise HTTP 404 for a missing document. File removal and database errors
    propagate; removing the file is not reversed if the database commit fails.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}
