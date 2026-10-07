"""arXiv API client (free, no key). stdlib only."""
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "https://export.arxiv.org/api/query"
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}
PAGE_SIZE = 20
CACHE_TTL = 600

_NEW_ID = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(?:v\d+)?(?![\d])")
_OLD_ID = re.compile(r"\b([a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?\b")

_cache: dict[str, tuple[float, dict]] = {}


class ArxivError(Exception):
    pass


def parse_id(text: str) -> str | None:
    """Pull a versionless arXiv id out of a bare id or any arxiv.org URL."""
    text = (text or "").strip()
    m = _NEW_ID.search(text) or _OLD_ID.search(text)
    return m.group(1) if m else None


def find_ids(text: str) -> set[str]:
    """Every arXiv id mentioned in a text. Bare numbers only count next to 'arxiv' to avoid matching decimals."""
    found = set()
    for m in _NEW_ID.finditer(text or ""):
        before = text[max(0, m.start() - 24):m.start()].lower()
        if "arxiv" in before:
            found.add(m.group(1))
    found.update(m.group(1) for m in _OLD_ID.finditer(text or "") if "arxiv" in text[max(0, m.start() - 24):m.start()].lower())
    return found


def looks_like_id(text: str) -> bool:
    """True when the whole input is an id or an arXiv link, not a keyword query."""
    text = (text or "").strip()
    if "arxiv.org" in text:
        return parse_id(text) is not None
    return bool(_NEW_ID.fullmatch(text) or _OLD_ID.fullmatch(text))


def build_query(query: str, category: str = "") -> str:
    # 필드 접두어·괄호 같은 arXiv 쿼리 문법은 지우고 단어와 "구문"만 남긴다
    query = re.sub(r'[^\w\s."+\-]', " ", query)
    parts = []
    for term in re.findall(r'"[^"]+"|[^\s"]+', query):
        clean = " ".join(term.strip('"').split())
        if not clean:
            continue
        parts.append(f'all:"{clean}"' if " " in clean else f"all:{clean}")
    q = " AND ".join(parts)
    if category:
        q = f"cat:{category} AND ({q})" if q else f"cat:{category}"
    return q


def _get(params: dict) -> dict:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return {**hit[1], "cached": True}
    req = urllib.request.Request(url, headers={"User-Agent": "paper-study/0.2 (local study tool)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read()
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            raise ArxivError("arXiv가 요청을 잠시 제한하고 있어요. 몇 초 뒤 다시 시도해주세요.") from e
        raise ArxivError(f"arXiv 응답 오류 (HTTP {e.code})") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ArxivError("arXiv에 연결하지 못했어요. 인터넷 연결을 확인해주세요.") from e
    try:
        result = parse_feed(body)
    except ET.ParseError as e:
        raise ArxivError("arXiv 응답을 해석하지 못했어요.") from e
    _cache[url] = (time.time(), result)
    return {**result, "cached": False}


def parse_feed(body: bytes | str) -> dict:
    root = ET.fromstring(body)
    items = []
    for entry in root.findall("a:entry", NS):
        arxiv_id = parse_id(entry.findtext("a:id", "", NS))
        title = " ".join(entry.findtext("a:title", "", NS).split())
        if not arxiv_id or not title:
            continue  # arXiv answers an unknown id with an empty "Error" entry
        published = entry.findtext("a:published", "", NS)[:10]
        primary = entry.find("arxiv:primary_category", NS)
        cats = [c.get("term") for c in entry.findall("a:category", NS) if c.get("term")]
        if primary is not None and primary.get("term") in cats:
            cats.remove(primary.get("term"))
            cats.insert(0, primary.get("term"))
        items.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": ", ".join(a.findtext("a:name", "", NS) for a in entry.findall("a:author", NS)),
            "year": int(published[:4]) if published[:4].isdigit() else None,
            "published": published,
            "published_at": entry.findtext("a:published", "", NS),
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "abstract": " ".join(entry.findtext("a:summary", "", NS).split()),
            "categories": ", ".join(cats),
            "comment": " ".join((entry.findtext("arxiv:comment", "", NS) or "").split()),
        })
    total = root.findtext("os:totalResults", "", NS)
    return {"total": int(total) if total.isdigit() else len(items), "items": items}


def search(query: str, sort: str = "relevance", category: str = "", start: int = 0) -> dict:
    q = build_query(query, category)
    if not q:
        return {"total": 0, "items": [], "cached": True}
    return _get({
        "search_query": q,
        "sortBy": "submittedDate" if sort == "recent" else "relevance",
        "sortOrder": "descending",
        "start": start,
        "max_results": PAGE_SIZE,
    })


def fetch(ids: list[str]) -> list[dict]:
    ids = [i for i in dict.fromkeys(parse_id(x) for x in ids) if i]
    if not ids:
        return []
    return _get({"id_list": ",".join(ids), "max_results": len(ids)})["items"]
