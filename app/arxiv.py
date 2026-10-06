"""arXiv API search - free, no key needed."""
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {"a": "http://www.w3.org/2005/Atom"}
API = "http://export.arxiv.org/api/query"


def search(query: str, max_results: int = 15):
    url = f"{API}?{urllib.parse.urlencode({'search_query': f'all:{query}', 'sortBy': 'relevance', 'max_results': max_results})}"
    with urllib.request.urlopen(url, timeout=15) as res:
        root = ET.fromstring(res.read())
    papers = []
    for entry in root.findall("a:entry", NS):
        link = entry.findtext("a:id", "", NS)
        papers.append({
            "title": " ".join(entry.findtext("a:title", "", NS).split()),
            "authors": ", ".join(a.findtext("a:name", "", NS) for a in entry.findall("a:author", NS)[:4]),
            "year": int(entry.findtext("a:published", "0000", NS)[:4]),
            "url": link,
            "abstract": " ".join(entry.findtext("a:summary", "", NS).split()),
        })
    return papers


if __name__ == "__main__":
    results = search("YOLO object detection", 3)
    assert len(results) == 3 and all(p["title"] and p["url"] for p in results)
    print("arxiv search OK:", results[0]["title"])
