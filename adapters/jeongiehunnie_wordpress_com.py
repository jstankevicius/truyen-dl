import re
from concurrent.futures import ProcessPoolExecutor
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from adapters.base import URLAdapter
from common import ChapterInfo


class JeongieHunnieAdapter(URLAdapter):
    """Adapter for jeongiehunnie.wordpress.com serialized novels."""

    def _get_html(self, url: str) -> BeautifulSoup:
        r = requests.get(url)
        r.raise_for_status()
        content = r.content.decode("utf-8")
        return BeautifulSoup(content, features="lxml")

    def _get_entry_content(self, soup: BeautifulSoup):
        entry = soup.find("div", attrs={"class": "entry-content"})
        if entry:
            return entry
        return soup.find("article") or soup

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _is_boilerplate(self, text: str) -> bool:
        lower = text.lower()
        return any(
            marker in lower
            for marker in [
                "share this",
                "published by",
                "leave a comment",
                "theo dõi",
                "additional links",
                "skip to content",
                "advertisement",
                "older comments",
                "comment",
                "reblog",
                "subscribe",
                "loading...tagged",
                "reply to",
                "reply",
                "published in",
                "posted in",
                "chia sẻ trên x",
                "chia sẻ lên facebook",
            ]
        )

    def _looks_like_chapter_link(self, text: str, href: str) -> bool:
        normalized = self._normalize_text(text)
        lower = normalized.lower()
        href_lower = href.lower()

        return bool(
            re.search(r"chương\s*\d+", lower)
            or re.search(r"ngoại truyện", lower)
            or re.search(r"niu-giu-chuong-\d+", href_lower)
            or re.search(r"niu-giu-ngoai-truyen", href_lower)
        )

    def _chapter_sort_key(self, text: str, href: str):
        normalized = self._normalize_text(text)
        lower = normalized.lower()
        href_lower = href.lower()

        match = re.search(r"chương\s*(\d+)", lower)
        if match:
            return (0, int(match.group(1)))

        match = re.search(r"ngoại truyện\s*(\d+)", lower)
        if match:
            return (1, int(match.group(1)))

        match = re.search(r"niu-giu-chuong-(\d+)", href_lower)
        if match:
            return (0, int(match.group(1)))

        match = re.search(r"niu-giu-ngoai-truyen-(\d+)", href_lower)
        if match:
            return (1, int(match.group(1)))

        match = re.search(r"niu-giu-ngoai-truyen-tru-nhiem-(\d+)", href_lower)
        if match:
            return (2, int(match.group(1)))

        match = re.search(r"niu-giu-ngoai-truyen-lan-dau-gap-nhau-(\d+)", href_lower)
        if match:
            return (3, int(match.group(1)))

        return None

    def get_book_title(self, url: str) -> str:
        soup = self._get_html(url)

        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return self._normalize_text(og_title["content"])

        title_elem = soup.find(attrs={"class": "entry-title"})
        if title_elem:
            return self._normalize_text(title_elem.get_text(" ", strip=True))

        if soup.title and soup.title.string:
            return self._normalize_text(soup.title.string)

        return "Unknown Title"

    def get_chapter_links_and_titles(self, url: str) -> list[tuple[str, str]]:
        soup = self._get_html(url)
        entry = self._get_entry_content(soup)

        links: list[tuple[str, str]] = []
        seen_urls: set[str] = set()

        for anchor in entry.find_all("a", href=True):
            chapter_url = urljoin(url, anchor["href"])
            if chapter_url in seen_urls:
                continue

            chapter_title = self._normalize_text(anchor.get_text(" ", strip=True))
            if not self._looks_like_chapter_link(chapter_title, chapter_url):
                continue

            seen_urls.add(chapter_url)
            links.append((chapter_url, chapter_title))

        print(f"Fetched {len(links)} chapter links")
        return links

    def get_chapter_info(self, url: str, index: int, title: str) -> ChapterInfo:
        try:
            soup = self._get_html(url)
            entry = self._get_entry_content(soup)

            chapter_title = title
            if not chapter_title:
                title_elem = soup.find(attrs={"class": "entry-title"})
                if title_elem:
                    chapter_title = self._normalize_text(title_elem.get_text(" ", strip=True))
                else:
                    chapter_title = f"Chương {index + 1}"

            chapter_lines: list[str] = []
            for block in entry.find_all(["p", "blockquote"]):
                text = self._normalize_text(block.get_text(" ", strip=True))
                if not text:
                    continue

                lower = text.lower()
                if lower.startswith(("chương sau", "next post", "previous post")):
                    break

                if self._is_boilerplate(text):
                    continue

                if chapter_title and text == chapter_title:
                    continue

                chapter_lines.append(text)

            if not chapter_lines:
                print(f"Warning: No content found for {url}")

            return ChapterInfo(title=chapter_title, body=chapter_lines, index=index)
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return ChapterInfo(title=title or f"Chương {index + 1}", body=[], index=index)

    def get_output_filename(self, url: str, title: str) -> str:
        name = url.rstrip("/").split("/")[-1]
        return f"{name}.epub"

    def fetch_chapters(
        self, links: list[tuple[str, str]], n_workers: int = 8
    ) -> list[ChapterInfo]:
        chapters = []
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            link_indexes = list(range(len(links)))
            urls = [link[0] for link in links]
            titles = [link[1] for link in links]
            results = executor.map(self.get_chapter_info, urls, link_indexes, titles)
            for info in tqdm(results, total=len(links), desc="Downloading"):
                chapters.append(info)

        chapters.sort(key=lambda info: info.index)
        return chapters
