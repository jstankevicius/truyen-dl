import requests
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm
import re

from adapters.base import URLAdapter
from common import ChapterInfo


class MongTruyenAdapter(URLAdapter):
    """Adapter for mongtruyen.com story downloads."""

    def _extract_lines_from_html(self, html: str) -> list[str]:
        fragment = BeautifulSoup(html, features="lxml")
        paragraphs = fragment.find_all("p")
        lines = []

        if paragraphs:
            for paragraph in paragraphs:
                text = paragraph.get_text(" ", strip=True)
                if text and "JavaScript" not in text and "Đang tải" not in text:
                    lines.append(text)
            return lines

        text = fragment.get_text("\n", strip=True)
        if text and "JavaScript" not in text and "Đang tải" not in text:
            return [line.strip() for line in text.splitlines() if line.strip()]

        return []

    def _get_html(self, url: str) -> BeautifulSoup:
        r = requests.get(url)
        r.raise_for_status()
        content = r.content.decode("utf-8")
        soup = BeautifulSoup(content, features="lxml")
        return soup

    def get_book_title(self, url: str) -> str:
        """Extract book title from the page."""
        soup = self._get_html(url)

        # Use page title or OG title
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title.get("content", "Unknown Title").strip()

        if soup.title:
            return soup.title.string.strip()

        return "Unknown Title"

    def _get_total_chapters(self, url: str) -> int:
        """Get the total number of chapters by scanning the breadcrumb navigation."""
        soup = self._get_html(url)
        breadcrumb = soup.find("div", attrs={"class": "mdv-breadcrumb-chuong-box"})

        if breadcrumb:
            # Look for chapter numbers in the breadcrumb text
            import re
            text = breadcrumb.get_text()
            chapters = re.findall(r'Chương\s+(\d+)', text)
            if chapters:
                # Get the maximum chapter number
                return max(int(x) for x in chapters)

        # Default to a reasonable number if we can't find it
        return 50

    def get_chapter_links_and_titles(self, url: str) -> list[tuple[str, str]]:
        """Generate chapter links based on URL pattern."""
        # Extract the base URL without query parameters
        base_url = url.split("?")[0]

        # Get the total number of chapters
        total_chapters = self._get_total_chapters(url)
        print(f"Found {total_chapters} chapters")

        # Generate chapter URLs with incrementing chapter numbers
        links = []
        for i in range(1, total_chapters + 1):
            chapter_url = f"{base_url}?chuong={i}"
            chapter_title = f"Chương {i}"
            links.append((chapter_url, chapter_title))

        print(f"Generated {len(links)} chapter links")
        return links

    def get_chapter_info(self, url: str, index: int, title: str) -> ChapterInfo:
        """Extract chapter content from a chapter page."""
        try:
            session = requests.Session()
            chapter_page = session.get(url)
            chapter_page.raise_for_status()
            soup = BeautifulSoup(chapter_page.content.decode("utf-8"), features="lxml")

            # Look for chapter title in the page
            chapter_title_elem = soup.find("div", attrs={"class": "mdv-san-pham-detail-chuong-title"})
            if chapter_title_elem:
                full_title = chapter_title_elem.get_text(strip=True)
                # Parse "Chương X: Title" format
                title = full_title

            chapter_lines = []
            content_div = soup.find("div", id="noi_dung_truyen")
            if content_div:
                nonce = content_div.get("data-mt-nonce", "")
                id_truyen = content_div.get("data-mt-id-truyen", "")
                id_chapter = content_div.get("data-mt-id-chapter", "")
                pnvn_token_match = re.search(
                    r'const\s+pnvnToken\s*=\s*"([^"]+)"', chapter_page.text
                )

                if pnvn_token_match and nonce and id_truyen and id_chapter:
                    response = session.post(
                        "https://mongtruyen.com/sources/ajax/load-chapter-content.php",
                        data={
                            "pnvn_token": pnvn_token_match.group(1),
                            "id_truyen": id_truyen,
                            "id_chapter": id_chapter,
                            "nonce": nonce,
                        },
                        headers={
                            "Referer": url,
                            "Origin": "https://mongtruyen.com",
                            "X-Requested-With": "XMLHttpRequest",
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("status") == "success" and payload.get("noi_dung"):
                        chapter_lines = self._extract_lines_from_html(payload["noi_dung"])

            if not chapter_lines:
                content_div = soup.find("div", attrs={"class": "msv-khung-truyen-noi-dung"})
                if content_div:
                    chapter_lines = self._extract_lines_from_html(str(content_div))

            if not chapter_lines:
                print(f"Warning: No content found for {url}")

            return ChapterInfo(title=title, body=chapter_lines, index=index)
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return ChapterInfo(title=title, body=[], index=index)

    def get_output_filename(self, url: str, title: str) -> str:
        """Generate output filename from URL."""
        # Extract the story slug from the URL
        name = url.split("/")[-1].split(".")[0]
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
