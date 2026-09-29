from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models import Document
from app.routers import documents

pytestmark = pytest.mark.unit


@pytest.fixture
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(documents, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(documents, "MAX_UPLOAD_SIZE", 4)
    return tmp_path


@pytest.mark.parametrize("content", [b"", b"1234"])
@pytest.mark.parametrize("mime", ["application/pdf", "text/plain", "image/png"])
async def test_upload_accepts_size_boundary_and_hides_storage_path(
    db: Mock,
    actor: SimpleNamespace,
    audit: Mock,
    upload_dir: Path,
    content: bytes,
    mime: str,
) -> None:
    file = UploadFile(
        filename="../../report.pdf",
        file=BytesIO(content),
        headers=Headers({"content-type": mime}),
    )
    result = await documents.upload_document(file, "company", 7, "Report", db, actor)
    doc = db.add.call_args.args[0]
    assert Path(doc.file_path).parent == upload_dir
    assert Path(doc.file_path).read_bytes() == content
    assert Path(doc.file_path).name != "report.pdf"
    assert result["file_size"] == len(content)
    assert (result["title"], result["mime_type"], result["uploaded_by"]) == (
        "Report",
        mime,
        actor.id,
    )
    assert (result["entity_type"], result["entity_id"]) == ("company", 7)
    assert "file_path" not in result
    db.commit.assert_called_once_with()


@pytest.mark.parametrize(
    "filename,mime,content,status",
    [
        ("", "text/plain", b"1", 400),
        ("file.exe", "application/octet-stream", b"1", 400),
        ("file.txt", "text/plain", b"12345", 413),
    ],
)
async def test_invalid_upload_leaves_no_file_or_database_write(
    db: Mock,
    actor: SimpleNamespace,
    upload_dir: Path,
    filename: str,
    mime: str,
    content: bytes,
    status: int,
) -> None:
    file = UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": mime}),
    )
    with pytest.raises(HTTPException) as error:
        await documents.upload_document(file, db=db, current_user=actor)
    assert error.value.status_code == status
    assert list(upload_dir.iterdir()) == []
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_get_document_returns_public_metadata(db: Mock, actor: SimpleNamespace) -> None:
    doc = Document(
        id=1,
        title="Report",
        filename="report.pdf",
        file_path="/private/report.pdf",
        file_size=4,
        mime_type="application/pdf",
        uploaded_by=42,
    )
    db.query.return_value.first.return_value = doc
    result = documents.get_document(1, db, actor)
    assert result["id"] == 1
    assert result["filename"] == "report.pdf"
    assert "file_path" not in result
    assert set(result) == {
        "id",
        "title",
        "filename",
        "file_size",
        "mime_type",
        "entity_type",
        "entity_id",
        "uploaded_by",
        "created_at",
    }
