import argparse
import re
import uuid

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from tqdm import tqdm


@dataclass(frozen=True)
class ChapterInfo:
    title: str
    body: list[str]
    index: int


def _get_html(url: str) -> BeautifulSoup:
    r = requests.get(url)
    r.raise_for_status()
    content = r.content.decode("utf-8")
    soup = BeautifulSoup(content, features="lxml")

    return soup


def _get_chapter_links(url: str, page: int) -> list[str]:
    soup = _get_html(f"{url}/trang-{page}")
    chapter_list = (
        soup.find(id="list-chapter").find(attrs={"class": "row"}).find_all("a")
    )
    links = [a["href"] for a in chapter_list]
    return links


def _get_book_chapter_info(url: str, index: int) -> ChapterInfo:
    # Fetch chapter located at 'url', assuming chapter's index (position) in the book
    # is 'index'.
    soup = _get_html(url)
    chapter_title = soup.find(attrs={"class": "chapter-title"}).text

    chapter_content = soup.find(id="chapter-c")
    chapter_lines = list(chapter_content.stripped_strings)

    return ChapterInfo(title=chapter_title, body=chapter_lines, index=index)


def _get_num_chapter_paginator_pages(page: BeautifulSoup) -> int:
    # Get number of pages in the chapter list's paginating element. Even if there are
    # more pages than buttons displayed, the last element will link to the last page.
    pagination = page.find(attrs={"class": "pagination pagination-sm"})
    page_links = pagination.find_all("a")
    n_pages = 1
    for link in page_links:
        link_text = link["href"]
        page_number = int(re.search("trang-([0-9]+)", link_text).group(1))
        n_pages = max(n_pages, page_number)

    return n_pages


def _get_links_to_all_chapters(url: str, n_pages: int) -> list[str]:
    chapter_links = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        page_args = list(range(1, n_pages + 1))
        name_args = [url] * len(page_args)
        results = executor.map(_get_chapter_links, name_args, page_args)
        for page_links in tqdm(results):
            chapter_links.extend(page_links)

    print(f"Fetched {len(chapter_links)} chapter links")
    return chapter_links


def _fetch_chapters(links: list[str], n_workers: int = 8) -> list[ChapterInfo]:
    chapters = []
    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        link_indexes = list(range(len(links)))
        results = executor.map(_get_book_chapter_info, links, link_indexes)
        for info in tqdm(results, total=len(links)):
            chapters.append(info)

    # Sort chapters by index to maintain correct order
    chapters.sort(key=lambda info: info.index)
    return chapters


def _write_epub(
    title: str, author: str, chapter_infos: list[ChapterInfo], outfile: str
) -> None:
    book = epub.EpubBook()

    # Generate a deterministic UUID based on the book URL
    # This ensures the same book always gets the same identifier
    book_uuid = uuid.uuid5(uuid.NAMESPACE_URL, title)
    book.set_identifier(f"urn:uuid:{book_uuid}")

    book.set_title(title)
    book.set_language("vi")
    book.add_author(author)

    chapters = []
    for info in chapter_infos:
        chapter = epub.EpubHtml(
            title=info.title, file_name=f"chapter-{info.index}.xhtml", lang="vi"
        )
        content = f"<h1>{info.title}</h1>"
        content += "\n".join([f"<p>{line}</p>" for line in info.body])
        chapter.content = content
        book.add_item(chapter)
        chapters.append(chapter)

    # Add navigation files
    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = ["nav"] + chapters
    epub.write_epub(outfile, book)


def download(url: str):
    soup = _get_html(url)

    # Extract proper title with all the tones and stuff
    book_title_pretty = (
        soup.find(attrs={"class": "breadcrumb"})
        .find(attrs={"class": "active"})
        .find(itemprop="name")
        .text
    )

    author = soup.find(itemprop="author").text
    n_pages = _get_num_chapter_paginator_pages(soup)

    # Fetch chapter links in parallel
    print(f"Fetching chapter links from {n_pages} pages...")
    chapter_links = _get_links_to_all_chapters(url, n_pages)

    # Download chapters in parallel
    print("Downloading chapters...")
    chapters = _fetch_chapters(chapter_links)

    name = [part for part in url.split("/") if len(part) > 0][-1]
    print(f"Writing {name}.epub")
    _write_epub(book_title_pretty, author, chapters, f"{name}.epub")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        help="URL of truyenfull.vision book landing page, e.g. 'https://truyenfull.vision/kiem-lai/'",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    download(args.url)


if __name__ == "__main__":
    main()
