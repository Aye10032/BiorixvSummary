import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from loguru import logger
from requests import RequestException, ReadTimeout
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3 import Retry

from util.decorator import retry


class ConsolidateHeader(StrEnum):
    NO_CONSOLIDATION = '0'
    ALL_METADATA = '1'
    CITATION_AND_DOI = '2'
    DOI_ONLY = '3'


class ConsolidateCitations(StrEnum):
    NO_CONSOLIDATION = '0'
    ALL_METADATA = '1'
    CITATION_AND_DOI = '2'


class ConsolidateFunders(StrEnum):
    NO_CONSOLIDATION = '0'
    ALL_METADATA = '1'
    CITATION_AND_DOI = '2'


@dataclass
class GrobidConfig:
    grobid_server: str
    service: str
    batch_size: int
    sleep_time: int
    timeout: int
    coordinates: list[str]
    multi_process: int

    @classmethod
    def from_dict(cls, data: dict[str, any]):
        return cls(**data)


class GrobidConnector:
    def __init__(self, config: GrobidConfig):
        self.server_url = f'{config.grobid_server}/api/{config.service}'
        self.check_url = f'{config.grobid_server}/api/isalive'
        self.coordinates = config.coordinates
        self.timeout = config.timeout
        self.batch_size = config.batch_size
        self.max_works = config.multi_process

    def __enter__(self):
        self._check_server_status()
        self.session = requests.Session()

        retries = Retry(total=5, backoff_factor=5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.session.headers.update({
            'User-Agent': 'GrobidConnector/1.0',
            'Accept': 'application/xml'
        })

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _check_server_status(self):
        try:
            response = requests.get(self.check_url)
            response.raise_for_status()
        except RequestException as e:
            logger.error(f'[{e}]: Grobid server is unavailable.')
            raise ConnectionError('Grobid server is unavailable.')

    def parse_file(
            self,
            pdf_file: str | bytes,
            *,
            consolidate_header: str = ConsolidateHeader.ALL_METADATA,
            consolidate_citations: str = ConsolidateCitations.ALL_METADATA,
            consolidate_funders: str = ConsolidateFunders.NO_CONSOLIDATION,
            include_raw_citations: bool = True,
            include_raw_affiliations: bool = False,
            include_raw_copyrights: bool = False,
            segment_sentences: bool = False,
            generate_ids: bool = False,
            start: int = -1,
            end: int = -1
    ) -> tuple[str | bytes, int, str]:
        """
        Convert the complete input document into TEI XML format (header, body and bibliographical section).

        :param pdf_file: The PDF file to be parsed. Can be a file path or bytes.
        :param consolidate_header: The level of header consolidation. Default is ALL_METADATA.
        :param consolidate_citations: The level of citation consolidation. Default is ALL_METADATA.
        :param consolidate_funders: The level of funder consolidation. Default is NO_CONSOLIDATION.
        :param include_raw_citations: Whether to include raw citations in the output. Default is False.
        :param include_raw_affiliations: Whether to include raw affiliations in the output. Default is False.
        :param include_raw_copyrights: Whether to include raw copyrights in the output. Default is False.
        :param segment_sentences: Whether to segment sentences in the output. Default is False.
        :param generate_ids: Whether to generate IDs in the output. Default is False.
        :param start: The start page for parsing. Default is -1 (no limit).
        :param end: The end page for parsing. Default is -1 (no limit).
        :return: A tuple containing the HTTP status code and the response text.
        """
        with open(pdf_file, 'rb') as f:
            files = {
                "input": (
                    pdf_file,
                    f,
                    "application/pdf",
                    {"Expires": "0"},
                )
            }

            the_data = {
                "consolidateHeader": consolidate_header,
                "consolidateCitations": consolidate_citations,
                "consolidateFunders": consolidate_funders,
                "teiCoordinates": self.coordinates,
                "start": start,
                "end": end,
                "includeRawCitations": "1" if include_raw_citations else "0",
                "includeRawAffiliations": "1" if include_raw_affiliations else "0",
                "includeRawCopyrights": "1" if include_raw_copyrights else "0",
                "segmentSentences": "1" if segment_sentences else "0",
                "generateIDs": "1" if generate_ids else "0"
            }

            response = self.session.post(self.server_url, files=files, data=the_data, timeout=self.timeout)
            return pdf_file, response.status_code, response.text

    def __default_parse(self, pdf_file: str | bytes):
        return self.parse_file(pdf_file)

    def parse_files(
            self,
            pdf_path: str | bytes,
            output_path: str | bytes,
            multi_process: bool = False,
            skip_exist: bool = False,
    ) -> None:
        file_list = [
            os.path.join(dir_path, filename)
            for dir_path, _, filenames in os.walk(pdf_path)
            for filename in filenames
            if filename.lower().endswith('.pdf')
        ]

        with tqdm(total=len(file_list), desc="Processing PDFs", unit="file") as pbar:
            if multi_process:
                for i in range(0, len(file_list), self.batch_size):
                    batch = file_list[i:i + self.batch_size]

                    with ThreadPoolExecutor(max_workers=self.max_works) as executor:
                        responses = [
                            executor.submit(
                                self.__default_parse,
                                file
                            ) for file in batch
                        ]

                        for response in as_completed(responses):
                            input_file, status, text = response.result()

                            if status == 200:
                                xml_file = os.path.join(
                                    output_path,
                                    Path(input_file).name.replace('.pdf', '.grobid.xml')
                                )
                                os.makedirs(output_path, exist_ok=True)
                                with open(xml_file, 'w', encoding='utf8') as f:
                                    f.write(text)
                            else:
                                logger.error(f'Parse {input_file} error.')

                            pbar.update(1)
            else:
                for file in file_list:
                    try:
                        xml_file = os.path.join(
                            output_path,
                            Path(file).name.replace('.pdf', '.grobid.xml')
                        )

                        if skip_exist and os.path.exists(xml_file) and os.path.getsize(xml_file) != 0:
                            continue

                        input_file, status, text = self.parse_file(file)

                        if status == 200:
                            os.makedirs(output_path, exist_ok=True)
                            with open(xml_file, 'w', encoding='utf8') as f:
                                f.write(text)
                        else:
                            logger.error(f'Parse {input_file} error.')
                    except ReadTimeout:
                        logger.error(f'timeout while parsing {file}')
                    finally:
                        pbar.update(1)


@retry(delay=1.0)
def parse_pdf(pdf_path: str) -> str:
    grobid_config = GrobidConfig(
        grobid_server="https://aye10032-grobid.hf.space",
        service="processFulltextDocument",
        batch_size=1000,
        sleep_time=5,
        timeout=300,
        coordinates=[
            "persName",
            "ref",
            "head",
            "s",
            "p",
            "title"
        ],
        multi_process=10
    )
    with GrobidConnector(grobid_config) as connector:
        _, result_code, xml_text = connector.parse_file(pdf_path)

    if result_code != 200:
        raise Exception('download error.')

    return xml_text


def check_title(title):
    pattern = re.compile(r'^(Introduction|Discussions|Conclusion?)$', re.IGNORECASE)
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
