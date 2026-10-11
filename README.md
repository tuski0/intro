# MSA 게시판 (FastAPI + Docker + AWS EC2)

배포 실습용 게시판입니다. 게시글/댓글 CRUD를 **서비스 2개로 분리**한 MSA 구조입니다.

## 아키텍처

```
                 ┌──────────────────── EC2 (Docker Compose) ────────────────────┐
                 │                                                               │
 Browser ──:80──▶│  frontend (Nginx)                                             │
                 │   ├─ /              → 정적 파일 (HTML/JS/CSS)                 │
                 │   ├─ /api/posts/*   → post-service:8000    ──┐                │
                 │   └─ /api/comments/*→ comment-service:8000 ──┤ (서비스 간 HTTP)│
                 │                                              │                │
                 │  post-service (FastAPI)  ◀───────────────────┘                │
                 │       └─ post_db                                              │
                 │  comment-service (FastAPI)                                    │
                 │       └─ comment_db          (PostgreSQL 16, 서비스별 DB 분리) │
                 └───────────────────────────────────────────────────────────────┘
```

| 서비스 | 역할 | 외부 노출 |
|---|---|---|
| `frontend` | Nginx. 정적 페이지 서빙 + API Gateway(경로 기반 라우팅) | 80 포트 |
| `post-service` | 게시글 CRUD. 글 삭제 시 comment-service에 댓글 정리 요청 | ✗ (Gateway 경유) |
| `comment-service` | 댓글 CRUD. 댓글 작성 시 post-service에 글 존재 여부 확인 | ✗ (Gateway 경유) |
| `db` | PostgreSQL. `post_db`, `comment_db` 분리 (Database per Service) | ✗ |

**MSA 포인트**
- 서비스마다 **독립된 코드, 이미지, DB**를 가집니다. 댓글 테이블은 게시글에 FK를 걸지 않고 `post_id`만 저장합니다.
- 다른 서비스의 데이터가 필요하면 **DB를 직접 보지 않고 HTTP API로 요청**합니다. (`httpx`)
- `/internal/*` API는 Nginx가 프록시하지 않으므로 서비스끼리만 호출할 수 있습니다.

## 기술 스택
- Python 3.12 (`python:3.12-slim`), FastAPI, SQLAlchemy 2.0, Pydantic v2, psycopg 3
- PostgreSQL 16, Nginx 1.27
- Docker, Docker Compose

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/posts?page=1&size=10` | 글 목록 |
| POST | `/api/posts` | 글 작성 `{title, content, author}` |
| GET | `/api/posts/{id}` | 글 상세 |
| PUT | `/api/posts/{id}` | 글 수정 `{title, content}` |
| DELETE | `/api/posts/{id}` | 글 삭제 (댓글도 함께 삭제) |
| GET | `/api/comments?post_id={id}` | 댓글 목록 |
| POST | `/api/comments` | 댓글 작성 `{post_id, author, content}` |
| DELETE | `/api/comments/{id}` | 댓글 삭제 |

Swagger 문서: `http://<주소>/api/posts/docs`, `http://<주소>/api/comments/docs`

---

## 1. 로컬에서 실행

```bash
cp .env.example .env
docker compose up -d --build
```

브라우저에서 http://localhost 접속. 종료: `docker compose down` (DB 데이터까지 지우려면 `-v` 추가)

## 2. AWS EC2에 배포

### 2-1. 인스턴스 생성 (AWS 콘솔 → EC2 → 인스턴스 시작)
- **AMI**: Ubuntu Server 24.04 LTS
- **인스턴스 유형**: `t3.micro` 또는 `t2.micro` (프리 티어 대상인지 확인)
- **키 페어**: 새로 만들고 `.pem` 파일을 잘 보관
- **보안 그룹 인바운드 규칙**
  | 유형 | 포트 | 소스 |
  |---|---|---|
  | SSH | 22 | 내 IP |
  | HTTP | 80 | 0.0.0.0/0 |

  > 8000, 5432 포트는 **열지 마세요.** 외부에는 Nginx(80)만 노출하는 게 이 구조의 핵심입니다.
- (권장) **탄력적 IP**를 할당해서 인스턴스에 연결하면 재시작해도 IP가 바뀌지 않습니다.

### 2-2. SSH 접속
```bash
chmod 400 my-key.pem
ssh -i my-key.pem ubuntu@<EC2_퍼블릭_IP>
```

### 2-3. Docker 설치 (EC2 안에서)
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit   # 그룹 적용을 위해 재접속
```
재접속 후 `docker compose version` 이 나오면 OK.

### 2-4. (1GB 메모리 인스턴스라면) 스왑 추가
빌드 중 메모리 부족으로 멈추는 것을 막아줍니다.
```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2-5. 코드 올리기
**방법 A — GitHub 사용 (권장)**
```bash
git clone https://github.com/<내계정>/board-msa.git
cd board-msa
```

**방법 B — 내 PC에서 직접 복사**
```bash
# 내 PC에서 실행
scp -i my-key.pem -r ./board-msa ubuntu@<EC2_퍼블릭_IP>:~/
```

### 2-6. 실행
```bash
cd ~/board-msa
cp .env.example .env
nano .env          # POSTGRES_PASSWORD를 꼭 바꾸기 (영문/숫자만)
docker compose up -d --build
docker compose ps  # 4개 컨테이너가 모두 running인지 확인
```

브라우저에서 `http://<EC2_퍼블릭_IP>` 접속 🎉

### 2-7. 코드 수정 후 재배포
```bash
git pull
docker compose up -d --build
```

## 3. 자주 쓰는 명령어 / 트러블슈팅

```bash
docker compose ps                         # 상태 확인
docker compose logs -f post-service       # 특정 서비스 로그
docker compose restart comment-service    # 특정 서비스만 재시작
docker compose exec db psql -U board -d post_db   # DB 접속
```

| 증상 | 확인할 것 |
|---|---|
| 브라우저에서 접속이 안 됨 | 보안 그룹에 80 포트 열었는지, `http://`로 접속했는지 (`https` 아님) |
| 502 Bad Gateway | `docker compose logs post-service` 로 백엔드 에러 확인 |
| DB 인증 실패 | `.env` 비밀번호를 바꾼 뒤라면 기존 볼륨에 예전 비밀번호가 남아 있음 → `docker compose down -v` 후 다시 실행 (데이터 삭제됨) |
| 빌드 중 멈춤 | 메모리 부족 → 2-4 스왑 추가 |

## 4. 다음 단계로 해볼 만한 것
- **도메인 + HTTPS**: Route 53 / 가비아 도메인 연결 → Certbot(Let's Encrypt)으로 SSL
- **이미지 레지스트리**: EC2에서 빌드하지 않고 ECR/Docker Hub에 이미지를 올려 `pull`만 하기
- **CI/CD**: GitHub Actions로 push 시 자동 배포
- **DB 분리**: PostgreSQL을 RDS로 옮기기
- **서비스 추가**: user-service(회원가입/JWT 로그인)를 추가해 MSA 확장

## 디렉터리 구조
```
board-msa/
├── compose.yaml
├── .env.example
├── db/init.sql                 # post_db, comment_db 생성
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf              # API Gateway 라우팅
│   └── html/ (index.html, app.js, style.css)
└── services/
    ├── post-service/
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   └── app/ (main.py, database.py, models.py, schemas.py)
    └── comment-service/
        └── (post-service와 동일한 구조)
```
