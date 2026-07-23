import uuid
from dataclasses import dataclass
from ebooklib import epub


@dataclass(frozen=True)
class ChapterInfo:
    title: str
    body: list[str]
    index: int


def write_epub(
    title: str, chapter_infos: list[ChapterInfo], outfile: str
) -> None:
    """Write a list of chapters to an EPUB file."""
    book = epub.EpubBook()

    # Generate a deterministic UUID based on the book title
    book_uuid = uuid.uuid5(uuid.NAMESPACE_URL, title)
    book.set_identifier(f"urn:uuid:{book_uuid}")

    book.set_title(title)
    book.set_language("vi")

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
