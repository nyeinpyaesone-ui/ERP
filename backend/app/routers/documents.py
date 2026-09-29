from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import shutil
import uuid

from app.database import get_db
from app.models import Document
from app.auth import get_current_user
from app.config import settings
from app.services.permissions import require_permission
from app.services.activity_log import log_activity

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

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    title: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("documents", "create"))
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")

    # Read file to check size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Max size: {MAX_UPLOAD_SIZE} bytes")

    file_ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    doc = Document(
        title=title or file.filename,
        filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=current_user.id
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_activity(db, user_id=current_user.id, action="document_uploaded", entity_type="document", entity_id=doc.id)
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
        "created_at": doc.created_at
    }

@router.get("/documents")
def list_documents(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("documents", "read"))
):
    if limit > 100:
        limit = 100
    query = db.query(Document)
    if entity_type:
        query = query.filter(Document.entity_type == entity_type)
    if entity_id:
        query = query.filter(Document.entity_id == entity_id)
    return query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

@router.get("/documents/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db), current_user = Depends(require_permission("documents", "read"))):
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
        "created_at": doc.created_at
    }

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), current_user = Depends(require_permission("documents", "delete"))):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}