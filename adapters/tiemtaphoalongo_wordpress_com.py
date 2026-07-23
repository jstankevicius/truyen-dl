import requests
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

from adapters.base import URLAdapter
from common import ChapterInfo


class WordPressAdapter(URLAdapter):
    """Adapter for WordPress sites hosting serialized novels."""

    def _get_html(self, url: str) -> BeautifulSoup:
        r = requests.get(url)
        r.raise_for_status()
        content = r.content.decode("utf-8")
        soup = BeautifulSoup(content, features="lxml")
        return soup

    def get_book_title(self, url: str) -> str:
        """Extract book title from the main page."""
        soup = self._get_html(url)
        
        # Try entry-title class first
        title_elem = soup.find(attrs={"class": "entry-title"})
        if title_elem:
            return title_elem.text.strip()
        
        # Fall back to page title
        if soup.title:
            return soup.title.string.strip()
        
        return "Unknown Title"

    def get_chapter_links_and_titles(self, url: str) -> list[tuple[str, str]]:
        """Fetch all chapter links and titles from the index page."""
        soup = self._get_html(url)
        links = []
        
        tbody = soup.find("tbody")
        if tbody:
            for a in tbody.find_all("a"):
                chapter_url = a["href"]
                chapter_title = a.get_text(strip=True)
                links.append((chapter_url, chapter_title))
        
        print(f"Fetched {len(links)} chapter links")
        return links

    def get_chapter_info(self, url: str, index: int, title: str) -> ChapterInfo:
        """Extract chapter content from a chapter page."""
        try:
            soup = self._get_html(url)
            entry = soup.find("div", attrs={"class": "entry-content"})
            
            if not entry:
                print(f"Could not find entry-content: {url}")
                return ChapterInfo(title=title or f"Chapter {index + 1}", body=[], index=index)
            
            # Get all paragraphs and filter out empty ones
            all_paragraphs = entry.find_all("p")
            chapter_lines = []
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                if text:
                    chapter_lines.append(text)
            
            if not chapter_lines:
                print(f"Could not get content: {url}")
            
            return ChapterInfo(title=title, body=chapter_lines, index=index)
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
            for info in tqdm(results, total=len(links)):
                chapters.append(info)
        
        # Sort chapters by index to maintain correct order
        chapters.sort(key=lambda info: info.index)
        return chapters
