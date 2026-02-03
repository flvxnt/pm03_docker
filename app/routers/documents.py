import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.rate_limit import rate_limiter
from app.core.logging import get_security_logger
from app.services.storage import sha256_file
from app.db.session import get_db
from app.db.models import Document, DocumentType, DocumentAccess, User, Role
from app.services.storage import save_upload
from app.services.audit import log_access
from app.core.config import settings
from app.core.deps import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents"])

sec_logger = get_security_logger()


def can_access_document(db: Session, user: User, doc: Document) -> bool:
    if user.role == Role.admin:
        return True
    if doc.owner_id == user.id:
        return True

    allowed = db.scalar(
        select(DocumentAccess).where(
            DocumentAccess.document_id == doc.id,
            DocumentAccess.user_id == user.id,
        )
    )
    return allowed is not None


@router.post("/upload")
def upload_document(
    request: Request,
    title: str = Query(..., min_length=1),
    doc_type: DocumentType = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate_limiter.check(request)

    stored_filename, full_path, sha256 = save_upload(file)

    # защита от повторной загрузки одинакового файла (для этого владельца)
    duplicate = db.scalar(
        select(Document).where(
            Document.owner_id == current_user.id,
            Document.file_sha256 == sha256,
        )
    )
    if duplicate:
        # удаляем лишний файл
        if os.path.exists(full_path):
            os.remove(full_path)

        sec_logger.warning(
            f"Duplicate upload blocked user={current_user.username} doc_id={duplicate.id}"
        )
        log_access(
            db=db,
            action="upload",
            success=False,
            user_id=current_user.id,
            document_id=None,
            reason="duplicate_upload",
            request=request,
        )
        raise HTTPException(status_code=409, detail="Duplicate file upload blocked")

    doc = Document(
        title=title,
        doc_type=doc_type,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_sha256=sha256,
        owner_id=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_access(
        db=db,
        action="upload",
        success=True,
        user_id=current_user.id,
        document_id=doc.id,
        request=request,
    )

    return {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "owner_id": doc.owner_id,
        "sha256": doc.file_sha256,
    }


@router.get("/")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi import HTTPException, Request
    from app.core.rate_limit import rate_limiter

    key = f"user:{current_user.id}"
    if not rate_limiter.check(key):
        raise HTTPException(status_code=429, detail="Too many requests")
    # показываем только доступные документы
    docs = db.scalars(select(Document).order_by(Document.id.desc())).all()

    visible = []
    for d in docs:
        if can_access_document(db, current_user, d):
            visible.append(
                {
                    "id": d.id,
                    "title": d.title,
                    "doc_type": d.doc_type,
                    "original_filename": d.original_filename,
                    "owner_id": d.owner_id,
                    "created_at": d.created_at,
                }
            )
    return visible


@router.post("/{doc_id}/grant")
def grant_access(
    doc_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # выдавать доступ может только владелец или админ
    if not (current_user.role == Role.admin or doc.owner_id == current_user.id):
        raise HTTPException(status_code=403, detail="No rights to grant access")

    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    exists = db.scalar(
        select(DocumentAccess).where(
            DocumentAccess.document_id == doc_id,
            DocumentAccess.user_id == user_id,
        )
    )
    if exists:
        return {"status": "already granted"}

    da = DocumentAccess(document_id=doc_id, user_id=user_id)
    db.add(da)
    db.commit()

    return {"status": "granted", "doc_id": doc_id, "user_id": user_id}


@router.get("/{doc_id}")
def get_document(
    request: Request,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate_limiter.check(request)
    doc = db.get(Document, doc_id)
    if not doc:
        log_access(db, "view", False, current_user.id, doc_id, "not_found", request)
        raise HTTPException(status_code=404, detail="Document not found")

    if not can_access_document(db, current_user, doc):
        log_access(db, "view", False, current_user.id, doc_id, "forbidden", request)
        raise HTTPException(status_code=403, detail="Access denied")

    log_access(db, "view", True, current_user.id, doc_id, None, request)

    file_path = os.path.join(settings.STORAGE_PATH, doc.stored_filename)
    if os.path.exists(file_path):
        current_hash = sha256_file(file_path)
        if current_hash != doc.file_sha256:
            sec_logger.error(f"Integrity FAIL doc_id={doc.id} user={current_user.username}")
            log_access(db, "view", False, current_user.id, doc_id, "integrity_fail", request)
            raise HTTPException(status_code=409, detail="Integrity check failed")

    return {
        "id": doc.id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "original_filename": doc.original_filename,
        "owner_id": doc.owner_id,
        "created_at": doc.created_at,
    }


@router.get("/{doc_id}/download")
def download_document(
    request: Request,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rate_limiter.check(request)
    doc = db.get(Document, doc_id)
    if not doc:
        log_access(db, "download", False, current_user.id, doc_id, "not_found", request)
        raise HTTPException(status_code=404, detail="Document not found")

    if not can_access_document(db, current_user, doc):
        log_access(db, "download", False, current_user.id, doc_id, "forbidden", request)
        raise HTTPException(status_code=403, detail="Access denied")

    file_path = os.path.join(settings.STORAGE_PATH, doc.stored_filename)
    if not os.path.exists(file_path):
        log_access(db, "download", False, current_user.id, doc_id, "file_missing", request)
        raise HTTPException(status_code=404, detail="File missing in storage")

    log_access(db, "download", True, current_user.id, doc_id, None, request)
    
    current_hash = sha256_file(file_path)
    if current_hash != doc.file_sha256:
        sec_logger.error(f"Integrity FAIL doc_id={doc.id} user={current_user.username}")
        log_access(db, "download", False, current_user.id, doc_id, "integrity_fail", request)
        raise HTTPException(status_code=409, detail="Integrity check failed")

    return FileResponse(
        path=file_path,
        filename=doc.original_filename,
        media_type="application/octet-stream",
    )


@router.delete("/{doc_id}")
def delete_document(
    request: Request,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.get(Document, doc_id)
    if not doc:
        log_access(db, "delete", False, current_user.id, doc_id, "not_found", request)
        raise HTTPException(status_code=404, detail="Document not found")

    # удалять может только владелец или админ
    if not (current_user.role == Role.admin or doc.owner_id == current_user.id):
        log_access(db, "delete", False, current_user.id, doc_id, "forbidden", request)
        raise HTTPException(status_code=403, detail="Access denied")

    file_path = os.path.join(settings.STORAGE_PATH, doc.stored_filename)

    db.delete(doc)
    db.commit()

    if os.path.exists(file_path):
        os.remove(file_path)

    log_access(db, "delete", True, current_user.id, doc_id, None, request)

    return {"status": "deleted", "id": doc_id}