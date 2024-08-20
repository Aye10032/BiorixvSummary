import os
import random
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

import requests
import urllib3
from loguru import logger
from pandas import DataFrame, Series

from path import get_work_path
from util.decorator import retry

CONTENT_ENDPOINT = 'https://api.biorxiv.org/details/biorxiv'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'


@dataclass
class Paper:
    doi: str
    title: str
    authors: str
    author_corresponding: str
    author_corresponding_institution: str
    date: str
    version: int
    type: str
    license: str
    category: str
    jatsxml: str
    abstract: str
    published: bool
    server: str
    more_graph: dict

    @classmethod
    def from_dict(cls, data: Series):
        data_dict = data.to_dict()
        version = int(data_dict.pop('version'))
        return cls(**data_dict, version=version, more_graph={})


class Category(StrEnum):
    AnimalBehaviorAndCognition = "animal behavior and cognition"
    Biochemistry = "biochemistry"
    Bioengineering = "bioengineering"
    Bioinformatics = "bioinformatics"
    Biophysics = "biophysics"
    CancerBiology = "cancer biology"
    CellBiology = "cell biology"
    ClinicalTrials = "clinical trials"
    DevelopmentalBiology = "developmental biology"
    Ecology = "ecology"
    Epidemiology = "epidemiology"
    EvolutionaryBiology = "evolutionary biology"
    Genetics = "genetics"
    Genomics = "genomics"
    Immunology = "immunology"
    Microbiology = "microbiology"
    MolecularBiology = "molecular biology"
    Neuroscience = "neuroscience"
    Paleontology = "paleontology"
    Pathology = "pathology"
    PharmacologyAndToxicology = "pharmacology and toxicology"
    Physiology = "physiology"
    PlantBiology = "plant biology"
    ScientificCommunicationAndEducation = "scientific communication and education"
    SyntheticBiology = "synthetic biology"
    SystemsBiology = "systems biology"
    Zoology = "zoology"


MAIN_LIST = [
    Category.Biochemistry.value,
    Category.Bioengineering,
    Category.Bioinformatics.value,
    Category.Biophysics.value,
    Category.CellBiology.value,
    Category.Genetics.value,
    Category.Genomics.value,
    Category.Microbiology.value,
    Category.MolecularBiology.value
]


@retry(delay=random.uniform(2.0, 5.0))
def get_daily_papers(yesterday: str) -> DataFrame:
    """Fetches the daily papers from BioRxiv for the previous day.

    Args:
        yesterday (str): The date of the previous day in the format 'YYYY-MM-DD'.

    Returns:
        DataFrame: A DataFrame containing the collection of papers.

    Raises:
        Exception: If the download of the information fails.
    """
    logger.info(f"开始下载{yesterday}的BioRxiv预印本信息...")
    url = f"{CONTENT_ENDPOINT}/{yesterday}/{yesterday}/0/json"
    payload = {}
    headers = {'User-Agent': USER_AGENT}

    response = requests.request("GET", url, headers=headers, data=payload).json()
    message: dict = response['messages'][0]
    if message['status'] == "ok":
        logger.info(f"下载完毕，"
                    f"{yesterday}共有{message['total']}篇预印本，"
                    f"其中有{message['count_new_papers']}篇有新动态")
    else:
        raise Exception("下载信息失败")

    return DataFrame(response['collection'])


@retry(delay=random.uniform(2.0, 5.0))
def download_pdf(base_path: str | bytes, doi: str) -> str:
    """
    Download the PDF of a paper from BioRxiv using its DOI.

    Args:
        base_path:
        doi (str): The DOI of the paper to download.

    Returns:
        str: The file path where the downloaded PDF is saved.

    Raises:
        Exception: If the PDF download fails.
    """
    url = f"https://www.biorxiv.org/content/{doi}v1.full.pdf"
    pdf_path = os.path.join(base_path, doi.replace('/', '@'), f"{doi.replace('/', '@')}.pdf")
    headers = {
        "User-Agent": USER_AGENT
    }

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    wget_command = ["wget", "-O", pdf_path, url]
    for header, value in headers.items():
        wget_command.extend(["--header", f"{header}: {value}"])

    result = subprocess.run(wget_command, capture_output=True)

    if result.returncode != 0:
        error_message = result.stderr.decode()
        logger.error(f"Failed to download PDF. Return code: {result.returncode}")
        raise Exception(f"下载PDF {url} 失败: {error_message}")

    return pdf_path


def main() -> None:
    download_pdf('./', '10.1101/2024.08.04.606512')


if __name__ == '__main__':
    main()
