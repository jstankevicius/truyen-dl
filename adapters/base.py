from abc import ABC, abstractmethod
from common import ChapterInfo


class URLAdapter(ABC):
    """Base class for URL-specific adapters that handle different websites."""

    @abstractmethod
    def get_book_title(self, url: str) -> str:
        """Extract the book title from the URL/page."""
        pass

    @abstractmethod
    def get_chapter_links_and_titles(self, url: str) -> list[tuple[str, str]]:
        """
        Fetch all chapter links and their titles from the index page.
        
        Returns:
            List of (chapter_url, chapter_title) tuples
        """
        pass

    @abstractmethod
    def get_chapter_info(self, url: str, index: int, title: str) -> ChapterInfo:
        """Extract chapter content and metadata from a chapter page."""
        pass

    @abstractmethod
    def get_output_filename(self, url: str, title: str) -> str:
        """Generate an output filename for the EPUB."""
        pass
