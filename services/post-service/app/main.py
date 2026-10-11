import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Post
from .schemas import PostCreate, PostList, PostOut, PostUpdate

COMMENT_SERVICE_URL = os.getenv("COMMENT_SERVICE_URL", "http://comment-service:8000")

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


# docs 경로를 /api/posts 아래에 두어 Gateway(Nginx)를 통해서도 Swagger를 볼 수 있게 함
app = FastAPI(
    title="Post Service",
    lifespan=lifespan,
    docs_url="/api/posts/docs",
    openapi_url="/api/posts/openapi.json",
)
router = APIRouter(prefix="/api/posts", tags=["posts"])


def get_post_or_404(post_id: int, db: Session) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "게시글을 찾을 수 없습니다.")
    return post


@router.get("", response_model=PostList)
def list_posts(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count()).select_from(Post))
    items = db.scalars(
        select(Post).order_by(Post.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return {"items": items, "total": total}


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(body: PostCreate, db: Session = Depends(get_db)):
    post = Post(**body.model_dump())
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    return get_post_or_404(post_id, db)


@router.put("/{post_id}", response_model=PostOut)
def update_post(post_id: int, body: PostUpdate, db: Session = Depends(get_db)):
    post = get_post_or_404(post_id, db)
    post.title = body.title
    post.content = body.content
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = get_post_or_404(post_id, db)
    db.delete(post)
    db.commit()

    # 서비스 간 통신: 댓글은 comment-service의 DB에 있으므로 API로 정리를 요청
    try:
        httpx.delete(
            f"{COMMENT_SERVICE_URL}/internal/posts/{post_id}/comments", timeout=3
        ).raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("댓글 정리 실패 (post_id=%s): %s", post_id, e)


app.include_router(router)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
