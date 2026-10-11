const app = document.getElementById("app");
const PAGE_SIZE = 10;

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (d) => new Date(d).toLocaleString("ko-KR");

// 모든 요청은 같은 origin의 /api/* 로 보내고, Nginx(Gateway)가 각 서비스로 라우팅
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) msg = typeof body.detail === "string" ? body.detail : body.detail.map((d) => d.msg).join(", ");
    } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

async function renderList(page) {
  const data = await api(`/api/posts?page=${page}&size=${PAGE_SIZE}`);
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  const rows = data.items
    .map(
      (p) => `
      <tr>
        <td class="col-id">${p.id}</td>
        <td><a href="#/posts/${p.id}">${esc(p.title)}</a></td>
        <td class="col-author">${esc(p.author)}</td>
        <td class="col-date">${fmt(p.created_at)}</td>
      </tr>`
    )
    .join("");

  const pager = Array.from({ length: pages }, (_, i) => i + 1)
    .map((n) => (n === page ? `<strong>${n}</strong>` : `<a href="#/?page=${n}">${n}</a>`))
    .join("");

  app.innerHTML = `
    <h2>게시글 목록 <small>총 ${data.total}개</small></h2>
    ${
      data.items.length
        ? `<table>
            <thead><tr><th class="col-id">번호</th><th>제목</th><th class="col-author">작성자</th><th class="col-date">작성일</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
          <nav class="pager">${pager}</nav>`
        : `<div class="card empty">아직 게시글이 없습니다. 첫 글을 작성해 보세요!</div>`
    }`;
}

async function renderDetail(id) {
  const [post, comments] = await Promise.all([
    api(`/api/posts/${id}`),
    api(`/api/comments?post_id=${id}`),
  ]);

  const edited = post.updated_at !== post.created_at ? ` · 수정 ${fmt(post.updated_at)}` : "";
  const commentItems = comments
    .map(
      (c) => `
      <li>
        <div class="head">
          <span><b>${esc(c.author)}</b> · ${fmt(c.created_at)}</span>
          <button class="btn small danger" data-comment-id="${c.id}">삭제</button>
        </div>
        <div class="body">${esc(c.content)}</div>
      </li>`
    )
    .join("");

  app.innerHTML = `
    <div class="card">
      <h2>${esc(post.title)}</h2>
      <div class="meta">${esc(post.author)} · ${fmt(post.created_at)}${edited}</div>
      <div class="content">${esc(post.content)}</div>
      <div class="actions">
        <a class="btn" href="#/">목록</a>
        <a class="btn" href="#/edit/${post.id}">수정</a>
        <button class="btn danger" id="delete-post">삭제</button>
      </div>
    </div>
    <div class="card comments">
      <h3>댓글 ${comments.length}</h3>
      <ul>${commentItems || `<li class="empty">첫 댓글을 남겨보세요.</li>`}</ul>
      <form class="comment-form" id="comment-form">
        <input name="author" placeholder="작성자" maxlength="50" required>
        <textarea name="content" placeholder="댓글 내용" maxlength="1000" required></textarea>
        <button class="btn primary" type="submit">등록</button>
      </form>
    </div>`;

  document.getElementById("delete-post").onclick = async () => {
    if (!confirm("이 글을 삭제할까요? 댓글도 함께 삭제됩니다.")) return;
    await api(`/api/posts/${id}`, { method: "DELETE" });
    location.hash = "#/";
  };

  app.querySelectorAll("[data-comment-id]").forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm("댓글을 삭제할까요?")) return;
      await api(`/api/comments/${btn.dataset.commentId}`, { method: "DELETE" });
      router();
    };
  });

  document.getElementById("comment-form").onsubmit = async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    try {
      await api("/api/comments", {
        method: "POST",
        body: JSON.stringify({ post_id: Number(id), author: form.get("author"), content: form.get("content") }),
      });
      router();
    } catch (err) {
      alert(err.message);
    }
  };
}

async function renderForm(id) {
  const post = id ? await api(`/api/posts/${id}`) : { title: "", author: "", content: "" };

  app.innerHTML = `
    <div class="card">
      <h2>${id ? "글 수정" : "새 글 작성"}</h2>
      <form id="post-form">
        <label>제목</label>
        <input name="title" maxlength="200" required value="${esc(post.title)}">
        <label>작성자</label>
        <input name="author" maxlength="50" required value="${esc(post.author)}" ${id ? "disabled" : ""}>
        <label>내용</label>
        <textarea name="content" required>${esc(post.content)}</textarea>
        <div class="actions">
          <a class="btn" href="${id ? `#/posts/${id}` : "#/"}">취소</a>
          <button class="btn primary" type="submit">${id ? "수정" : "등록"}</button>
        </div>
      </form>
    </div>`;

  document.getElementById("post-form").onsubmit = async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const body = { title: form.get("title"), content: form.get("content") };
    try {
      const saved = id
        ? await api(`/api/posts/${id}`, { method: "PUT", body: JSON.stringify(body) })
        : await api("/api/posts", { method: "POST", body: JSON.stringify({ ...body, author: form.get("author") }) });
      location.hash = `#/posts/${saved.id}`;
    } catch (err) {
      alert(err.message);
    }
  };
}

async function router() {
  const [path, query] = (location.hash.slice(1) || "/").split("?");
  const params = new URLSearchParams(query);
  let m;
  try {
    if (path === "/") await renderList(Number(params.get("page")) || 1);
    else if (path === "/new") await renderForm();
    else if ((m = path.match(/^\/posts\/(\d+)$/))) await renderDetail(m[1]);
    else if ((m = path.match(/^\/edit\/(\d+)$/))) await renderForm(m[1]);
    else app.innerHTML = `<div class="card empty">페이지를 찾을 수 없습니다.</div>`;
  } catch (err) {
    app.innerHTML = `<div class="error">오류: ${esc(err.message)}</div>`;
  }
}

window.addEventListener("hashchange", router);
router();
