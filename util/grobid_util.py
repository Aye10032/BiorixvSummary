import re

from bs4 import BeautifulSoup
from grobid_client.grobid_client import GrobidClient

from util.decorator import retry


@retry(delay=1.0)
def parse_pdf(pdf_path: str) -> str:
    client = GrobidClient(config_path='grobid.json')
    result = client.process_pdf(
        "processFulltextDocument",
        pdf_path,
        False,
        True,
        False,
        False,
        False,
        False,
        False
    )

    return result[2]


def check_title(title):
    pattern = re.compile(r'^(Introduction|Discussions?)$', re.IGNORECASE)
    return bool(pattern.match(title))


def extract_paragraphs(xml: str) -> dict:
    soup = BeautifulSoup(xml, 'xml')
    paragraphs = soup.find('body').find_all('div', recursive=False)

    result = {}
    for paragraph in paragraphs:
        if paragraph.find('head') is None:
            continue

        title = paragraph.find('head').text.strip()
        if check_title(title):

            text_list = []
            for p in paragraph.find_all('p'):
                text_list.append(p.text.strip())

            result[title] = '\n'.join(text_list)

    return result


def main() -> None:
    xml_str = parse_pdf("../test/2024.07.31.606043v1.full.pdf")
    extract_paragraphs(xml_str)


if __name__ == '__main__':
    main()
