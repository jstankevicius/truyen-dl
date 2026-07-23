import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

from adapters.base import URLAdapter
from common import ChapterInfo


class TruyenFullAdapter(URLAdapter):
    """Adapter for truyenfull.vision book downloads."""

    _headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://truyenfull.live/",
    }

    def _get_html(self, url: str) -> BeautifulSoup:
        r = requests.get(url, headers=self._headers, timeout=20)
        r.raise_for_status()
        content = r.content.decode("utf-8")
        soup = BeautifulSoup(content, features="lxml")
        return soup

    def get_book_title(self, url: str) -> str:
        """Extract book title from the main page."""
        soup = self._get_html(url)

        # Extract title from breadcrumb
        breadcrumb = soup.find(attrs={"class": "breadcrumb"})
        if breadcrumb:
            active = breadcrumb.find(attrs={"class": "active"})
            if active:
                name_elem = active.find(itemprop="name")
                if name_elem:
                    return name_elem.text.strip()

        return "Unknown Title"

    def _get_num_chapter_paginator_pages(self, page: BeautifulSoup) -> int:
        """Get number of pages in the chapter list's paginating element."""
        pagination = page.find(attrs={"class": "pagination pagination-sm"})
        if not pagination:
            return 1
        page_links = pagination.find_all("a")
        n_pages = 1
        for link in page_links:
            link_text = link["href"]
            match = re.search("trang-([0-9]+)", link_text)
            if match:
                page_number = int(match.group(1))
                n_pages = max(n_pages, page_number)

        return n_pages

    def _get_chapter_links(self, url: str, page: int) -> list[tuple[str, str]]:
        """Get chapter links and titles from a paginated page."""
        soup = self._get_html(f"{url}/trang-{page}")
        chapter_list = (
            soup.find(id="list-chapter").find(attrs={"class": "row"}).find_all("a")
        )
        links = [(a["href"], a.get_text(strip=True)) for a in chapter_list]
        return links

    def get_chapter_links_and_titles(self, url: str) -> list[tuple[str, str]]:
        """Fetch all chapter links and titles from all pages."""
        soup = self._get_html(url)
        n_pages = self._get_num_chapter_paginator_pages(soup)

        chapter_links = []
        with ProcessPoolExecutor(max_workers=8) as executor:
            page_args = list(range(1, n_pages + 1))
            name_args = [url] * len(page_args)
            results = executor.map(self._get_chapter_links, name_args, page_args)
            for page_links in tqdm(results, desc="Fetching pages"):
                chapter_links.extend(page_links)

        print(f"Fetched {len(chapter_links)} chapter links")
        return chapter_links

    def get_chapter_info(self, url: str, index: int, title: str) -> ChapterInfo:
        """Extract chapter content from a chapter page."""
        try:
            soup = self._get_html(url)
            chapter_title = soup.find(attrs={"class": "chapter-title"}).text.strip()

            chapter_content = soup.find(id="chapter-c")
            if chapter_content:
                chapter_lines = list(chapter_content.stripped_strings)
            else:
                chapter_lines = []

            return ChapterInfo(title=chapter_title, body=chapter_lines, index=index)
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return ChapterInfo(title=title, body=[], index=index)

    def get_output_filename(self, url: str, title: str) -> str:
        """Generate output filename from URL."""
        name = [part for part in url.split("/") if len(part) > 0][-1]
        return f"{name}.epub"

    def fetch_chapters(self, links: list[tuple[str, str]], n_workers: int = 8) -> list[ChapterInfo]:
        """Download all chapters in parallel."""
        chapters = []
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            link_indexes = list(range(len(links)))
            urls = [link[0] for link in links]
            titles = [link[1] for link in links]
            results = executor.map(self.get_chapter_info, urls, link_indexes, titles)
            for info in tqdm(results, total=len(links), desc="Downloading"):
                chapters.append(info)

        # Sort chapters by index to maintain correct order
        chapters.sort(key=lambda info: info.index)
        return chapters
