from pathlib import Path
from typing import Any, Dict, List
import json

from tools.browser_agent import BrowserAgent


class SearchResult:
    def __init__(self, title: str, url: str, snippet: str, content: str):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.content = content

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "content": self.content,
        }


class LocalSearchRAG:
    def __init__(self, max_pages: int = 5, max_chars: int = 4000, storage_dir: str = "data/frontier"):
        self.browser = BrowserAgent()
        self.max_pages = max_pages
        self.max_chars = max_chars
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_path = self.storage_dir / "search_embeddings.json"
        self._index: Dict[str, List[str]] = {}
        self._load_index()

    def _load_index(self) -> None:
        if self.embeddings_path.exists():
            try:
                self._index = json.loads(self.embeddings_path.read_text(encoding="utf-8"))
            except Exception:
                self._index = {}

    def build_search_url(self, query: str) -> str:
        from urllib.parse import quote_plus
        return f"https://duckduckgo.com/html/?q={quote_plus(query)}"

    def search(self, query: str) -> Dict[str, Any]:
        search_url = self.build_search_url(query)
        page_result = self.browser.fetch_page(search_url)
        if not page_result.get("success"):
            return {"status": "error", "error": page_result.get("error")}
        results = self._parse_results(page_result.get("content", ""))
        return {"status": "ok", "query": query, "results": [r.to_dict() for r in results[: self.max_pages]]}

    def fetch_and_summarize(self, query: str) -> Dict[str, Any]:
        search_out = self.search(query)
        if search_out.get("status") != "ok":
            return search_out
        summaries: List[str] = []
        stored: Dict[str, List[str]] = {}
        for result in search_out.get("results", [])[: self.max_pages]:
            fetched = self.browser.fetch_page(result["url"])
            if fetched.get("success"):
                text = fetched.get("content", "")[: self.max_chars]
                summaries.append(f"Title: {result['title']}\nURL: {result['url']}\n{text}")
                stored[result["url"]] = [result["title"], text]
        self._store_search(query, stored)
        return {
            "status": "ok",
            "query": query,
            "summaries": summaries,
            "sources": len(summaries),
            "storage_path": str(self.embeddings_path),
        }

    def semantic_search(self, query: str) -> Dict[str, Any]:
        matches: List[Dict[str, Any]] = []
        terms = [term.lower() for term in query.split() if term]
        for doc_id, fields in self._index.items():
            title, text = fields[0], fields[1] if len(fields) > 1 else ""
            haystack = f"{title} {text}".lower()
            hits = [term for term in terms if term in haystack]
            if hits:
                matches.append({"doc_id": doc_id, "title": title, "score": len(hits)})
        matches.sort(key=lambda x: x["score"], reverse=True)
        return {"status": "ok", "query": query, "matches": matches[: self.max_pages]}

    def _store_search(self, query: str, docs: Dict[str, List[str]]) -> None:
        self._index[query] = [doc for fields in docs.values() for doc in fields]
        try:
            self.embeddings_path.write_text(json.dumps(self._index, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            pass

    def _parse_results(self, page_text: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        i = 0
        while i < len(lines) - 2 and len(results) < self.max_pages:
            title = lines[i]
            snippet = lines[i + 1]
            url = lines[i + 2]
            if (url.startswith("http://") or url.startswith("https://")) and " " not in url.strip():
                results.append(SearchResult(title=title, url=url, snippet=snippet, content=""))
                i += 3
            else:
                i += 1
        return results
