import os
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Comment
from .schemas import CommentCreate, CommentOut

POST_SERVICE_URL = os.getenv("POST_SERVICE_URL", "http://post-service:8000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Comment Service",
    lifespan=lifespan,
    docs_url="/api/comments/docs",
    openapi_url="/api/comments/openapi.json",
)
router = APIRouter(prefix="/api/comments", tags=["comments"])


def ensure_post_exists(post_id: int) -> None:
    """서비스 간 통신: post-service에 게시글이 실제로 있는지 확인"""
    try:
        res = httpx.get(f"{POST_SERVICE_URL}/api/posts/{post_id}", timeout=3)
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "post-service에 연결할 수 없습니다.")
    if res.status_code == 404:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "게시글을 찾을 수 없습니다.")
    if res.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "post-service 응답 오류")


@router.get("", response_model=list[CommentOut])
def list_comments(post_id: int = Query(...), db: Session = Depends(get_db)):
    return db.scalars(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.id)
    ).all()


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(body: CommentCreate, db: Session = Depends(get_db)):
    ensure_post_exists(body.post_id)
    comment = Comment(**body.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "댓글을 찾을 수 없습니다.")
    db.delete(comment)
    db.commit()


app.include_router(router)


# 내부 전용 API: Nginx는 /api/* 만 프록시하므로 외부에서는 호출할 수 없음
@app.delete("/internal/posts/{post_id}/comments", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def delete_comments_of_post(post_id: int, db: Session = Depends(get_db)):
    db.execute(delete(Comment).where(Comment.post_id == post_id))
    db.commit()


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
