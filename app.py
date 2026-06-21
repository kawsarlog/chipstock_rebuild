"""
Chipstock main website — marketing pages + vyrian_db product catalog.

Run: python app.py
DB:  vyrian_db @ localhost:5432 (postgres / no password) — public.products table
"""
from __future__ import annotations

import base64
import datetime
import html as _html
import json
import math
import os
import re
import urllib.error
import urllib.request
from email.utils import parseaddr
from typing import Any, Dict, Generator, List, Optional, Tuple
from urllib.parse import urlparse

import functools
import uuid

import psycopg2
import psycopg2.pool
from flask import (
    Flask, Response, abort, flash, jsonify, redirect,
    render_template, request, session, url_for,
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chipstock-v2-secret")

# ── Catalog DB ───────────────────────────────────────────────────────────────
_DB = dict(
    host=os.getenv("PGHOST", "localhost"),
    dbname=os.getenv("PGDATABASE", "vyrian_db"),
    user=os.getenv("PGUSER", "postgres"),
    password=os.getenv("PGPASSWORD", ""),
    connect_timeout=10,
)

PER_PAGE = 24
SEARCH_MAX = 120

SORT_KEYS = {"name_asc", "name_desc", "mfr_asc"}
_ORDER: Dict[str, str] = {
    "name_asc":  "LOWER(COALESCE(description,'')) ASC  NULLS LAST, product_id",
    "name_desc": "LOWER(COALESCE(description,'')) DESC NULLS LAST, product_id",
    "mfr_asc":   "LOWER(COALESCE(manufacturer,'')) ASC NULLS LAST, product_id",
}

# (key, label, db_column_or_None, db_value_or_None)
CATEGORY_OPTIONS: List[Tuple[str, str, Optional[str], Optional[str]]] = [
    ("ALL",           "All Products",    None,       None),
    ("SEMICONDUCTORS","Semiconductors",  "source",   "vyrian"),
    ("HARD_DRIVES",   "Hard Drives",     "category", "HARD_DRIVES"),
    ("SSD",           "SSD",             "category", "SSD"),
    ("PROCESSORS",    "Processors",      "category", "PROCESSORS"),
    ("MEMORY",        "Memory",          "category", "MEMORY"),
]

# Readable labels for semiconductor IC sub-categories (vyrian lowercase category values)
SUBCAT_LABELS: Dict[str, str] = {
    "memory-ics":                    "Memory ICs",
    "programmable-ics":              "Programmable ICs",
    "transistors":                   "Transistors",
    "diodes":                        "Diodes",
    "logic-ics":                     "Logic ICs",
    "peripheral-ics":                "Peripheral ICs",
    "interface-ics":                 "Interface ICs",
    "amplifiers":                    "Amplifiers",
    "regulators":                    "Regulators",
    "capacitors":                    "Capacitors",
    "converters":                    "Converters",
    "optoelectronics":               "Optoelectronics",
    "resistors":                     "Resistors",
    "connectors":                    "Connectors",
    "inductors":                     "Inductors",
    "telecommunications":            "Telecom ICs",
    "sensors-transducers":           "Sensors & Transducers",
    "general-purpose-ics":           "General Purpose ICs",
    "filters":                       "Filters",
    "rf-microwave":                  "RF / Microwave",
    "triggering-devices":            "Triggering Devices",
    "relays":                        "Relays",
    "transformers":                  "Transformers",
    "storage-drives":                "Storage Drives",
    "other-function-semiconductors": "Other Semiconductors",
}


_pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10, **_DB)


def _conn():
    c = _pool.getconn()
    c.autocommit = False
    return c


def _put(c):
    try:
        _pool.putconn(c)
    except Exception:
        pass


# ── Admin / Blog ─────────────────────────────────────────────────────────────
ADMIN_USER = "admin"
ADMIN_PASS = "Chipstock@2025"
BLOG_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads", "blog")
ALLOWED_IMG = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
os.makedirs(BLOG_UPLOAD_DIR, exist_ok=True)


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


def _blog_get_all(include_drafts=False):
    db = _conn()
    try:
        with db.cursor() as cur:
            cond = "" if include_drafts else "WHERE status = 'published'"
            cur.execute(f"""
                SELECT id, title, slug, excerpt, featured_image, author, category,
                       tags, status, created_at, published_at
                FROM blog_posts {cond}
                ORDER BY COALESCE(published_at, created_at) DESC
            """)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        _put(db)


def _blog_get_slug(slug):
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, title, slug, excerpt, content, featured_image, author,
                       category, tags, seo_title, seo_description, status, created_at, published_at
                FROM blog_posts WHERE slug = %s
            """, (slug,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    finally:
        _put(db)


def _blog_get_id(post_id):
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT id, title, slug, excerpt, content, featured_image, author,
                       category, tags, seo_title, seo_description, status, created_at, published_at
                FROM blog_posts WHERE id = %s
            """, (post_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    finally:
        _put(db)


def _blog_create(data):
    db = _conn()
    try:
        with db.cursor() as cur:
            pub_at = datetime.datetime.utcnow() if data.get("status") == "published" else None
            cur.execute("""
                INSERT INTO blog_posts (title, slug, excerpt, content, featured_image,
                    author, category, tags, seo_title, seo_description, status, published_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (
                data["title"], data["slug"], data.get("excerpt"), data.get("content"),
                data.get("featured_image"), data.get("author", "Chipstock Team"),
                data.get("category"), data.get("tags", []),
                data.get("seo_title") or data["title"],
                data.get("seo_description") or data.get("excerpt", ""),
                data.get("status", "draft"), pub_at,
            ))
            post_id = cur.fetchone()[0]
        db.commit()
        return post_id
    except Exception:
        db.rollback()
        raise
    finally:
        _put(db)


def _blog_update(post_id, data):
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT status, published_at FROM blog_posts WHERE id=%s", (post_id,))
            row = cur.fetchone()
            pub_at = row[1] if row else None
            if data.get("status") == "published" and pub_at is None:
                pub_at = datetime.datetime.utcnow()
            cur.execute("""
                UPDATE blog_posts SET
                    title=%s, slug=%s, excerpt=%s, content=%s, featured_image=%s,
                    author=%s, category=%s, tags=%s, seo_title=%s, seo_description=%s,
                    status=%s, published_at=%s, updated_at=NOW()
                WHERE id=%s
            """, (
                data["title"], data["slug"], data.get("excerpt"), data.get("content"),
                data.get("featured_image"), data.get("author", "Chipstock Team"),
                data.get("category"), data.get("tags", []),
                data.get("seo_title") or data["title"],
                data.get("seo_description") or data.get("excerpt", ""),
                data.get("status", "draft"), pub_at, post_id,
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        _put(db)


def _blog_delete(post_id):
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM blog_posts WHERE id=%s", (post_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        _put(db)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())[:SEARCH_MAX]


def _cat_clause(cat_key: str) -> Tuple[str, List[Any]]:
    for k, _lbl, col, val in CATEGORY_OPTIONS:
        if k == cat_key:
            return (f"{col} = %s", [val]) if col else ("1=1", [])
    return ("1=1", [])


def fetch_catalog_page(
    cat_key: str, page: int, sort: str,
    mfr: Optional[str] = None, q: Optional[str] = None, subcat: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    order = _ORDER.get(sort, _ORDER["name_asc"])
    cat_cond, params = _cat_clause(cat_key)
    clauses: List[str] = ([cat_cond] if cat_cond != "1=1" else [])

    if subcat:
        clauses.append("category = %s")
        params.append(subcat)

    if mfr:
        clauses.append("LOWER(TRIM(COALESCE(manufacturer,'')))=LOWER(TRIM(%s))")
        params.append(mfr)

    nq = (q or "").strip()[:SEARCH_MAX]
    if nq:
        clauses.append(
            "(product_id ILIKE %s OR manufacturer ILIKE %s OR description ILIKE %s)"
        )
        params += [f"%{nq}%"] * 3

    where = " AND ".join(clauses) if clauses else "1=1"
    offset = (page - 1) * PER_PAGE

    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM public.products WHERE {where}", params)
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""SELECT product_id, manufacturer, description, image_url,
                           category, subcategory, source
                    FROM public.products WHERE {where}
                    ORDER BY {order} LIMIT %s OFFSET %s""",
                params + [PER_PAGE, offset],
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        db.commit()
        return rows, total
    except Exception:
        db.rollback()
        raise
    finally:
        _put(db)


def fetch_subcats(cat_key: str) -> List[Tuple[str, str]]:
    """Return [(db_val, label)] for component-type dropdown (semiconductors only)."""
    if cat_key not in ("ALL", "SEMICONDUCTORS"):
        return []
    extra = "source = 'vyrian' AND " if cat_key == "SEMICONDUCTORS" else ""
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                f"SELECT category, count(*) FROM public.products "
                f"WHERE {extra}category IS NOT NULL "
                f"AND category = lower(category) "
                f"GROUP BY category HAVING count(*) > 50 ORDER BY count(*) DESC"
            )
            return [
                (r[0], SUBCAT_LABELS.get(r[0], r[0].replace("-", " ").title()))
                for r in cur.fetchall()
            ]
    finally:
        _put(db)


def fetch_manufacturers(cat_key: str, subcat: Optional[str] = None) -> List[str]:
    cat_cond, params = _cat_clause(cat_key)
    clauses = [f"({cat_cond})"] if cat_cond != "1=1" else []
    if subcat:
        clauses.append("category = %s")
        params.append(subcat)
    clauses.append("TRIM(COALESCE(manufacturer,''))<>''")
    where = " AND ".join(clauses)
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                f"SELECT TRIM(manufacturer) AS m, count(*) FROM public.products "
                f"WHERE {where} GROUP BY TRIM(manufacturer) ORDER BY count(*) DESC LIMIT 300",
                params,
            )
            return [r[0] for r in cur.fetchall() if r[0]]
    finally:
        _put(db)


def fetch_related(pid: str, manufacturer: Optional[str], category: Optional[str], source: Optional[str] = None, limit: int = 5) -> List[Dict]:
    """Fetch similar products: same category → same manufacturer → same source (random fallback)."""
    COLS = "product_id, manufacturer, description, image_url, category"
    db = _conn()
    try:
        with db.cursor() as cur:
            results: list = []

            # 1) Same category, manufacturer priority
            if category:
                cur.execute(
                    f"""SELECT {COLS} FROM public.products
                        WHERE product_id <> %s AND category = %s
                        ORDER BY (LOWER(COALESCE(manufacturer,''))=LOWER(COALESCE(%s,''))) DESC, product_id
                        LIMIT %s""",
                    (pid, category, manufacturer or "", limit),
                )
                results = list(cur.fetchall())

            # 2) Same manufacturer, any category
            if len(results) < limit and manufacturer:
                seen = [r[0] for r in results] or ["__none__"]
                cur.execute(
                    f"""SELECT {COLS} FROM public.products
                        WHERE product_id <> %s
                          AND LOWER(TRIM(COALESCE(manufacturer,''))) = LOWER(TRIM(%s))
                          AND product_id <> ALL(%s)
                        ORDER BY product_id
                        LIMIT %s""",
                    (pid, manufacturer, seen, limit - len(results)),
                )
                results += list(cur.fetchall())

            # 3) Same source, fill — uses index on source
            if len(results) < limit:
                seen = [r[0] for r in results] or ["__none__"]
                src_cond = "AND source = %s" if source else ""
                src_val  = [source] if source else []
                cur.execute(
                    f"""SELECT {COLS} FROM public.products
                        WHERE product_id <> %s
                          AND product_id <> ALL(%s)
                          AND image_url IS NOT NULL
                          {src_cond}
                        ORDER BY product_id
                        LIMIT %s""",
                    [pid, seen] + src_val + [limit - len(results)],
                )
                results += list(cur.fetchall())

            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in results[:limit]]
    except Exception:
        return []
    finally:
        _put(db)


def fetch_product(pid: str) -> Optional[Dict]:
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT product_id, manufacturer, description, image_url,
                          specs_html, category, subcategory, source, updated_at
                   FROM public.products WHERE product_id = %s""",
                (pid,),
            )
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None
    finally:
        _put(db)


def _page_nums(cur: int, total: int) -> List:
    if total <= 1:
        return [1]
    if total <= 12:
        return list(range(1, total + 1))
    want = {1, total, cur, cur - 1, cur + 1, cur - 2, cur + 2}
    nums = sorted(p for p in want if 1 <= p <= total)
    out: List = []
    last = None
    for p in nums:
        if last and p > last + 1:
            out.append("…")
        out.append(p)
        last = p
    return out


# ── Brevo email ──────────────────────────────────────────────────────────────
def _valid_email(v: str) -> bool:
    _, addr = parseaddr((v or "").strip())
    if not addr or "@" not in addr or addr.count("@") != 1:
        return False
    local, domain = addr.rsplit("@", 1)
    return bool(local and domain and "." in domain and " " not in addr)


def _send_brevo(payload: Dict[str, str]) -> Tuple[bool, str]:
    api_key = (os.getenv("BREVO_API_KEY") or "").strip()
    if not api_key:
        return False, "Brevo API key not configured."
    sender = os.getenv("RFQ_FROM_EMAIL", "updates.from.kawsar@gmail.com")
    recipient = os.getenv("RFQ_TO_EMAIL", "rfq@chip-stock.com")
    esc = _html.escape
    msg_html = esc(payload["message"]).replace("\n", "<br>")
    html_body = f"""<html><body style="background:#0B0B0B;font-family:sans-serif;color:#f4f4f4;padding:24px;">
<table style="max-width:600px;width:100%">
<tr><td colspan="2" style="padding-bottom:16px">
  <h2 style="color:#B6F223;margin:0">New RFQ — Chipstock</h2></td></tr>
<tr><td style="color:#999;padding:6px 12px 6px 0">Name</td><td><b>{esc(payload['name'])}</b></td></tr>
<tr><td style="color:#999;padding:6px 12px 6px 0">Phone</td><td><b>{esc(payload['phone'])}</b></td></tr>
<tr><td style="color:#999;padding:6px 12px 6px 0">Email</td><td><b>{esc(payload['email'])}</b></td></tr>
<tr><td style="color:#999;padding:6px 12px 6px 0">Quantity</td><td><b>{esc(payload['quantity'])}</b></td></tr>
<tr><td style="color:#999;padding:6px 12px 6px 0">Part Number</td><td><b>{esc(payload.get('part_number') or '—')}</b></td></tr>
<tr><td style="color:#999;padding:6px 12px 6px 0">Product</td><td><b>{esc(payload.get('product_name') or '—')}</b></td></tr>
<tr><td style="color:#999;padding:6px 12px 6px 0">Page</td>
    <td><a href="{esc(payload.get('page_url',''))}" style="color:#B6F223">{esc(payload.get('page_url','—'))}</a></td></tr>
</table>
<div style="margin-top:16px;padding:12px;border:1px solid #333;background:#111">
  <div style="color:#B6F223;font-size:12px;text-transform:uppercase;margin-bottom:8px">Message</div>
  <div style="color:#eee;line-height:1.65">{msg_html}</div>
</div>
</body></html>"""
    body = {
        "sender":     {"name": "Chipstock", "email": sender},
        "to":         [{"email": recipient, "name": "Sales Team"}],
        "subject":    f"RFQ: {payload.get('product_name') or payload['name']}",
        "replyTo":    {"email": payload["email"], "name": payload["name"]},
        "htmlContent": html_body,
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "api-key": api_key,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return (200 <= resp.status < 300), ""
    except urllib.error.HTTPError as e:
        try:
            d = json.loads(e.read().decode())
            msg = str(d.get("message") or "")
        except Exception:
            msg = ""
        return False, f"Brevo {e.code}: {msg}"
    except Exception as e:
        return False, str(e)


# ── Marketing routes ─────────────────────────────────────────────────────────
@app.route("/")
def index():
    latest_posts = _blog_get_all(include_drafts=False)[:4]
    return render_template("index.html", latest_posts=latest_posts)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/products")
def products():
    return render_template("products.html")


@app.route("/quality")
def quality():
    return render_template("quality.html")


@app.route("/services")
def services():
    return render_template("services.html")


@app.route("/services/excess-inventory-management")
def excess():
    return render_template("excess.html")


@app.route("/news")
def news():
    posts = _blog_get_all(include_drafts=False)
    return render_template("news.html", posts=posts)


@app.route("/news/<slug>")
def news_post(slug):
    post = _blog_get_slug(slug)
    if not post or post["status"] != "published":
        abort(404)
    recent = [p for p in _blog_get_all() if p["slug"] != slug][:4]
    return render_template("news_post.html", post=post, recent=recent)


# ── Admin ─────────────────────────────────────────────────────────────────────
@app.route("/admin")
def admin_index():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return redirect(url_for("admin_posts"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if (request.form.get("username") == ADMIN_USER and
                request.form.get("password") == ADMIN_PASS):
            session["admin_logged_in"] = True
            session.permanent = True
            return redirect(url_for("admin_posts"))
        error = "Invalid username or password."
    return render_template("admin/login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/posts")
@login_required
def admin_posts():
    posts = _blog_get_all(include_drafts=True)
    return render_template("admin/posts.html", posts=posts)


@app.route("/admin/posts/new", methods=["GET", "POST"])
@login_required
def admin_post_new():
    if request.method == "POST":
        tags_raw = request.form.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data = {
            "title": request.form["title"],
            "slug": request.form["slug"],
            "excerpt": request.form.get("excerpt", ""),
            "content": request.form.get("content", ""),
            "featured_image": request.form.get("featured_image", ""),
            "author": request.form.get("author", "Chipstock Team"),
            "category": request.form.get("category", ""),
            "tags": tags,
            "seo_title": request.form.get("seo_title", ""),
            "seo_description": request.form.get("seo_description", ""),
            "status": request.form.get("status", "draft"),
        }
        _blog_create(data)
        flash("Post created successfully.", "success")
        return redirect(url_for("admin_posts"))
    return render_template("admin/post_editor.html", post=None)


@app.route("/admin/posts/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def admin_post_edit(post_id):
    post = _blog_get_id(post_id)
    if not post:
        abort(404)
    if request.method == "POST":
        tags_raw = request.form.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        data = {
            "title": request.form["title"],
            "slug": request.form["slug"],
            "excerpt": request.form.get("excerpt", ""),
            "content": request.form.get("content", ""),
            "featured_image": request.form.get("featured_image", ""),
            "author": request.form.get("author", "Chipstock Team"),
            "category": request.form.get("category", ""),
            "tags": tags,
            "seo_title": request.form.get("seo_title", ""),
            "seo_description": request.form.get("seo_description", ""),
            "status": request.form.get("status", "draft"),
        }
        _blog_update(post_id, data)
        flash("Post updated successfully.", "success")
        return redirect(url_for("admin_posts"))
    return render_template("admin/post_editor.html", post=post)


@app.route("/admin/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def admin_post_delete(post_id):
    _blog_delete(post_id)
    flash("Post deleted.", "success")
    return redirect(url_for("admin_posts"))


@app.route("/admin/upload-image", methods=["POST"])
@login_required
def admin_upload_image():
    f = request.files.get("image")
    if not f:
        return jsonify({"error": "No file"}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_IMG:
        return jsonify({"error": "File type not allowed"}), 400
    fname = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(BLOG_UPLOAD_DIR, fname))
    return jsonify({"url": f"/static/uploads/blog/{fname}"})


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/contact/submit", methods=["POST"])
def contact_submit():
    f = request.form
    name = (f.get("name") or "").strip()
    email = (f.get("email") or "").strip()
    if not name or not _valid_email(email):
        flash("Please provide your name and a valid email address.", "error")
        return redirect(request.referrer or url_for("contact"))

    company = (f.get("company") or "").strip()
    msg = (f.get("message") or "").strip()
    if company:
        msg = f"Company: {company}\n\n{msg}" if msg else f"Company: {company}"

    payload = {
        "name":         name,
        "phone":        (f.get("phone") or "").strip(),
        "email":        email,
        "quantity":     (f.get("quantity") or "").strip(),
        "part_number":  (f.get("part_number") or "").strip(),
        "message":      msg or "(Contact / quote request — no message provided)",
        "product_name": "Contact / Quote Request",
        "page_url":     request.referrer or "",
    }
    ok, _err = _send_brevo(payload)
    if ok:
        flash("Thank you! We will get back to you shortly.", "success")
    else:
        flash("Sorry, we couldn't send your request right now. Please email rfq@chip-stock.com directly.", "error")
    return redirect(request.referrer or url_for("contact"))


@app.route("/excess/submit", methods=["POST"])
def excess_submit():
    f = request.form
    name = (f.get("name") or "").strip()
    email = (f.get("email") or "").strip()
    if not name or not _valid_email(email):
        flash("Please provide your name and a valid email address.", "error")
        return redirect(url_for("excess"))

    company = (f.get("company") or "").strip()
    lines = []
    if company:
        lines.append(f"Company: {company}")
    csv_file = request.files.get("csv_file")
    if csv_file and csv_file.filename:
        lines.append(f"CSV uploaded: {secure_filename(csv_file.filename)}")
    lines.append("Excess inventory offer submitted via website form.")

    payload = {
        "name":         name,
        "phone":        (f.get("phone") or "").strip(),
        "email":        email,
        "quantity":     (f.get("quantity") or "").strip(),
        "part_number":  (f.get("part_number") or "").strip(),
        "message":      "\n".join(lines),
        "product_name": "Excess Inventory Offer",
        "page_url":     request.referrer or "",
    }
    ok, _err = _send_brevo(payload)
    if ok:
        flash("Thank you! We will review your inventory list and get back to you shortly.", "success")
    else:
        flash("Sorry, we couldn't send your request right now. Please email rfq@chip-stock.com directly.", "error")
    return redirect(url_for("excess"))


# ── Image proxy (serversupply.com) ───────────────────────────────────────────
def _img_b64enc(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

def _img_b64dec(s: str) -> str:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad).decode()

@app.route("/catalog-img/<token>")
def catalog_image_proxy(token: str) -> Response:
    try:
        url = _img_b64dec(token).strip()
    except Exception:
        abort(404)
    if not url.startswith(("http://", "https://")):
        abort(404)
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    if not (host == "serversupply.com" or host.endswith(".serversupply.com")):
        abort(403)
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; ChipstockCatalog/1.1)"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            ct = (resp.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip()
            data = resp.read()
    except Exception:
        abort(502)
    r = Response(data, mimetype=ct if ct.startswith("image/") else "image/jpeg")
    r.headers["Cache-Control"] = "public, max-age=604800"
    return r

@app.template_filter("proxy_img")
def proxy_img_filter(url: Optional[str]) -> str:
    """Wrap serversupply.com image URLs through the local proxy."""
    if not url:
        return ""
    host = (urlparse(url).netloc or "").lower().split(":")[0]
    if not (host == "serversupply.com" or host.endswith(".serversupply.com")):
        return url
    return url_for("catalog_image_proxy", token=_img_b64enc(url))


# ── Catalog routes ────────────────────────────────────────────────────────────
@app.route("/catalog")
def catalog():
    q = request.args.get("q", "").strip()[:SEARCH_MAX]
    cat_key = request.args.get("cat", "ALL").strip().upper()
    if not any(k == cat_key for k, *_ in CATEGORY_OPTIONS):
        cat_key = "ALL"
    sort = request.args.get("sort", "name_asc")
    if sort not in SORT_KEYS:
        sort = "name_asc"
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    # Sub-category filter (IC type — only for SEMICONDUCTORS / ALL tabs)
    available_subcats = fetch_subcats(cat_key)
    subcat_raw = request.args.get("subcat", "").strip()
    subcat = subcat_raw if any(k == subcat_raw for k, _ in available_subcats) else ""

    mfr_raw = request.args.get("mfr", "").strip()
    mfrs = fetch_manufacturers(cat_key, subcat or None)
    mfr_f = mfr_raw if any(m.lower() == mfr_raw.lower() for m in mfrs) else None

    rows, total = fetch_catalog_page(cat_key, page, sort, mfr=mfr_f, q=q or None, subcat=subcat or None)
    total_pages = max(1, math.ceil(total / PER_PAGE)) if total else 1
    if page > total_pages:
        page = total_pages

    cat_label = next((lbl for k, lbl, *_ in CATEGORY_OPTIONS if k == cat_key), "All Products")

    return render_template(
        "catalog.html",
        rows=rows, total=total, page=page, total_pages=total_pages,
        showing_from=(page - 1) * PER_PAGE + 1 if total else 0,
        showing_to=min(page * PER_PAGE, total),
        page_numbers=_page_nums(page, total_pages),
        cat_key=cat_key, cat_label=cat_label, sort=sort, q=q,
        manufacturers=mfrs, mfr_filter=mfr_f or "",
        category_options=CATEGORY_OPTIONS,
        available_subcats=available_subcats, subcat=subcat,
    )


@app.route("/catalog/<path:product_id>")
def catalog_detail(product_id: str):
    product = fetch_product(product_id)
    if not product:
        abort(404)
    related = fetch_related(
        product_id,
        product.get("manufacturer"),
        product.get("category"),
        source=product.get("source"),
    )
    return render_template("catalog_detail.html", product=product, related=related)


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()[:80]
    nq = _norm(q)
    if not nq:
        return jsonify([])
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT product_id, manufacturer, description
                   FROM public.products
                   WHERE regexp_replace(lower(COALESCE(product_id,'')), '[^a-z0-9]', '', 'g') LIKE %s
                      OR regexp_replace(lower(COALESCE(description,'')), '[^a-z0-9]', '', 'g') LIKE %s
                   LIMIT 8""",
                [f"%{nq}%"] * 2,
            )
            return jsonify([
                {"pid": r[0], "mfr": r[1] or "", "desc": (r[2] or "")[:70]}
                for r in cur.fetchall()
            ])
    except Exception:
        return jsonify([])
    finally:
        _put(db)


@app.route("/api/request-quote", methods=["POST"])
def request_quote():
    data = request.get_json(silent=True) or {}
    fields = {
        k: str(data.get(k) or "").strip()
        for k in ("name", "phone", "email", "quantity", "part_number",
                  "message", "product_name", "page_url")
    }
    missing = [k for k in ("name", "phone", "email", "quantity", "message") if not fields[k]]
    if missing:
        return jsonify({"ok": False, "error": "Please fill in all required fields."}), 400
    if not _valid_email(fields["email"]):
        return jsonify({"ok": False, "error": "Please provide a valid email address."}), 400
    if len(fields["message"]) > 5000:
        return jsonify({"ok": False, "error": "Message is too long."}), 400
    ok, err = _send_brevo(fields)
    if not ok:
        return jsonify({"ok": False, "error": err or "Failed to send."}), 500
    return jsonify({"ok": True})


@app.route("/thank-you")
def thank_you():
    return render_template("thank_you.html")


# ── Sitemap ──────────────────────────────────────────────────────────────────

SITE_BASE      = "https://chipstock.com"
SITEMAP_CHUNK  = 50_000   # max URLs per sitemap file (Google limit: 50k)

_STATIC_PAGES: List[Tuple[str, str, str]] = [
    ("/",                                                    "1.0", "weekly"),
    ("/catalog",                                             "0.9", "daily"),
    ("/services",                                            "0.8", "monthly"),
    ("/about",                                               "0.7", "monthly"),
    ("/quality",                                             "0.7", "monthly"),
    ("/products",                                            "0.8", "monthly"),
    ("/news",                                                "0.7", "weekly"),
    ("/contact",                                             "0.7", "monthly"),
    ("/services/excess-inventory-management",                "0.7", "monthly"),
    ("/news/chip-stock-named-2025-top-north-american-independent-distributors", "0.6", "monthly"),
    ("/news/chip-stock-top-electronic-component-distributor-semiconductor-review", "0.6", "monthly"),
    ("/news/chip-stock-named-top-20-global-independent-distributor-electronics-sourcing", "0.6", "monthly"),
]


@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /catalog-img/\n"
        "Disallow: /api/\n"
        f"\nSitemap: {SITE_BASE}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_index():
    db = _conn()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.products")
            total: int = cur.fetchone()[0]
    finally:
        _put(db)

    num_chunks = math.ceil(total / SITEMAP_CHUNK)
    today = datetime.date.today().isoformat()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f'  <sitemap><loc>{SITE_BASE}/sitemap-pages.xml</loc><lastmod>{today}</lastmod></sitemap>',
    ]
    for i in range(1, num_chunks + 1):
        lines.append(
            f'  <sitemap><loc>{SITE_BASE}/sitemap-products-{i}.xml</loc>'
            f'<lastmod>{today}</lastmod></sitemap>'
        )
    lines.append('</sitemapindex>')
    return Response("\n".join(lines), mimetype="application/xml")


@app.route("/sitemap-pages.xml")
def sitemap_pages():
    today = datetime.date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, priority, changefreq in _STATIC_PAGES:
        loc = _html.escape(f"{SITE_BASE}{path}")
        lines.append(
            f'  <url><loc>{loc}</loc><lastmod>{today}</lastmod>'
            f'<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>'
        )
    lines.append('</urlset>')
    return Response("\n".join(lines), mimetype="application/xml")


@app.route("/sitemap-products-<int:chunk>.xml")
def sitemap_products(chunk: int):
    if chunk < 1:
        abort(404)
    offset = (chunk - 1) * SITEMAP_CHUNK

    def _generate() -> Generator[str, None, None]:
        yield '<?xml version="1.0" encoding="UTF-8"?>\n'
        yield '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        db = _conn()
        try:
            with db.cursor("sitemap_cursor") as cur:  # server-side cursor
                cur.execute(
                    """SELECT product_id, updated_at FROM public.products
                       ORDER BY product_id
                       LIMIT %s OFFSET %s""",
                    (SITEMAP_CHUNK, offset),
                )
                while True:
                    rows = cur.fetchmany(5000)
                    if not rows:
                        break
                    for pid, updated_at in rows:
                        safe_pid = _html.escape(str(pid))
                        loc = f"{SITE_BASE}/catalog/{safe_pid}"
                        lastmod = (
                            f"<lastmod>{updated_at.date().isoformat()}</lastmod>"
                            if updated_at else ""
                        )
                        yield (
                            f"  <url><loc>{loc}</loc>{lastmod}"
                            f"<changefreq>monthly</changefreq>"
                            f"<priority>0.5</priority></url>\n"
                        )
        finally:
            _put(db)
        yield '</urlset>\n'

    # Check chunk exists (quick count check)
    db2 = _conn()
    try:
        with db2.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.products")
            total = cur.fetchone()[0]
    finally:
        db2.close()

    if offset >= total:
        abort(404)

    return Response(_generate(), mimetype="application/xml")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", 5001)))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
