import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

import requests
from loguru import logger
from pandas import DataFrame, Series

from path import get_work_path
from util.decorator import retry

CONTENT_ENDPOINT = 'https://api.biorxiv.org/details/biorxiv'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


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


@retry(delay=random.uniform(2.0, 5.0))
def get_daily_papers() -> DataFrame:
    """
    Fetches the daily papers from BioRxiv for the previous day.

    Returns:
        DataFrame: A DataFrame containing the collection of papers.

    Raises:
        Exception: If the download of the information fails.
    """
    logger.info(f"开始下载{YESTERDAY}的BioRxiv预印本信息...")
    url = f"{CONTENT_ENDPOINT}/{YESTERDAY}/{YESTERDAY}/0/json"
    payload = {}
    headers = {'User-Agent': USER_AGENT}

    response = requests.request("GET", url, headers=headers, data=payload).json()
    message: dict = response['messages'][0]
    if message['status'] == "ok":
        logger.info(f"下载完毕，"
                    f"{YESTERDAY}共有{message['total']}篇预印本信息更新，"
                    f"其中有{message['count_new_papers']}篇新发布")
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
    response = requests.get(url)

    if response.status_code == 200:
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        with open(pdf_path, 'wb') as file:
            file.write(response.content)
    else:
        logger.error(f"Failed to download PDF. HTTP status code: {response.status_code}")
        raise Exception("下载PDF失败")

    return pdf_path
