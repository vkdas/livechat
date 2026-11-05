import io
import logging
import os
import re
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from . import llm, net
from .config import (BLOG_URL, MAX_FILES_PER_POST, MAX_IMAGES_PER_POST, OCR_IMAGES,
                     PDF_MAX_OCR_PAGES, PDF_OCR)

log = logging.getLogger("extract")

FILE_EXT = {".pdf", ".docx", ".txt", ".md", ".csv"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MIN_IMAGE_BYTES = 8000

# Blogger stores images uploaded to a post on these hosts. They are part of the site's own
# posts, so images (and only images) from them are allowed.
MEDIA_HOSTS = ("blogger.googleusercontent.com", "bp.blogspot.com", "googleusercontent.com")


def _bare(host: str) -> str:
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_own_host(host: str) -> bool:
    """True only for the configured site (and its subdomains)."""
    mine = _bare(urlparse(BLOG_URL).hostname or "")
    h = _bare(host)
    return bool(mine) and (h == mine or h.endswith("." + mine))


def is_own_media_host(host: str) -> bool:
    h = _bare(host)
    return is_own_host(h) or any(h == m or h.endswith("." + m) for m in MEDIA_HOSTS)


def html_to_text(html, base: str = "", keep_links: bool = False):
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    links = [urljoin(base, a["href"]) for a in soup.find_all("a", href=True)]
    imgs = [urljoin(base, i["src"]) for i in soup.find_all("img", src=True)]
    if keep_links:
        for a in soup.find_all("a", href=True):
            href = urljoin(base, a["href"])
            label = a.get_text(" ", strip=True)
            if href.startswith("http") and label and label != href:
                a.append(f" ({href})")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text("\n")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text, links, imgs


def _upscale(url: str) -> str:
    return re.sub(r"/(?:s\d+|w\d+-h\d+)(?:-[a-z])*(?:-c)?/", "/s1600/", url)


@dataclass
class Attachment:
    url: str
    group: str  # file | image


def find_attachments(links: list[str], imgs: list[str], base_url: str) -> list[Attachment]:
    """Files and images that belong to this site only. Everything else is ignored."""
    seen: set[str] = set()
    files: list[Attachment] = []
    images: list[Attachment] = []

    def add(bucket, url, group):
        if url not in seen:
            seen.add(url)
            bucket.append(Attachment(url, group))

    for u in links:
        if not u.startswith("http"):
            continue
        host = urlparse(u).hostname or ""
        ext = os.path.splitext(urlparse(u).path)[1].lower()
        if ext in FILE_EXT and is_own_host(host):
            add(files, u, "file")
        elif ext in IMG_EXT and is_own_media_host(host):
            add(images, _upscale(u), "image")
    for u in imgs:
        if u.startswith("http") and is_own_media_host(urlparse(u).hostname or ""):
            add(images, _upscale(u), "image")

    out = files[:MAX_FILES_PER_POST]
    if OCR_IMAGES:
        out += images[:MAX_IMAGES_PER_POST]
    return out


def extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    n_pages = len(reader.pages)
    text = ""
    if PDF_OCR != "always":
        text = "\n\n".join((p.extract_text() or "") for p in reader.pages).strip()
    need_ocr = PDF_OCR == "always" or (PDF_OCR == "auto" and len(text) < 80 * max(1, n_pages))
    if need_ocr and PDF_OCR != "never":
        if n_pages > PDF_MAX_OCR_PAGES:
            log.warning("PDF has %s pages, skipping OCR", n_pages)
        else:
            try:
                ocr_text = llm.ocr(data, "application/pdf")
                if len(ocr_text) > len(text):
                    text = ocr_text
            except Exception as exc:
                log.warning("pdf ocr failed: %s", exc)
    return text


def extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for t in doc.tables:
        for row in t.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


def fetch_attachment(att: Attachment):
    """Returns dict(url, title, kind, text) or None. Every hop, including redirects, must stay on the site."""
    allow = is_own_media_host if att.group == "image" else is_own_host
    data, ct, final = net.get(att.url, allow=allow)
    path = urlparse(final).path
    ext = os.path.splitext(path)[1].lower()
    name = unquote(os.path.basename(path)) or "file"

    if att.group == "image":
        if not ct.startswith("image/") or len(data) < MIN_IMAGE_BYTES or not OCR_IMAGES:
            return None
        return dict(url=att.url, title=f"Image: {name}", kind="image", text=llm.ocr(data, ct))
    if ct == "application/pdf" or ext == ".pdf":
        return dict(url=att.url, title=name, kind="pdf", text=extract_pdf(data))
    if ext == ".docx" or "wordprocessingml" in ct:
        return dict(url=att.url, title=name, kind="docx", text=extract_docx(data))
    if ct.startswith("text/plain") or ext in (".txt", ".md", ".csv"):
        return dict(url=att.url, title=name, kind="text", text=data.decode("utf-8", "ignore"))
    return None
