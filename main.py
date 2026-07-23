import argparse
from urllib.parse import urlparse

from adapters import get_adapter
from common import write_epub


def download_book(url: str):
    """Download a book from the given URL and convert to EPUB."""
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    
    # Get the appropriate adapter for this domain
    print(f"Loading adapter for {parsed.netloc}...")
    adapter = get_adapter(url)
    print(f"Using adapter: {adapter.__class__.__name__}")
    
    # Fetch book title
    print("Fetching book title...")
    book_title = adapter.get_book_title(url)
    print(f"Book title: {book_title}")
    
    # Fetch chapter links
    print("Fetching chapter links...")
    chapter_links = adapter.get_chapter_links_and_titles(url)
    print(f"Found {len(chapter_links)} chapters")
    
    # Download chapters in parallel
    print("Downloading chapters...")
    chapters = adapter.fetch_chapters(chapter_links)
    
    # Write EPUB
    output_filename = adapter.get_output_filename(url, book_title)
    print(f"Writing {output_filename}")
    write_epub(book_title, chapters, output_filename)
    print("Done!")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download a serialized novel from supported websites and convert to EPUB"
    )
    parser.add_argument(
        "url",
        help="URL of the book index page (e.g., https://tiamtaphoalongo.wordpress.com/ngay-mai-van-yeu-em-mong-tieu-nhi/)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        download_book(args.url)
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
