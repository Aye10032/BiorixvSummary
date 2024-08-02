from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

import requests
from loguru import logger
from pandas import DataFrame, Series
from tqdm import tqdm

CONTENT_ENDPOINT = 'https://api.biorxiv.org/details/biorxiv'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


@dataclass
class Paper:
    doi: str
    title: str
    authors: list[str]
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

    @classmethod
    def from_dict(cls, data: Series):
        data_dict = data.to_dict()
        version = int(data_dict.pop('version'))
        return cls(**data_dict, version=version)


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


def get_daily_papers() -> DataFrame:
    """Retrieve the daily papers from BioRxiv.

    Returns:

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


def main() -> None:
    paper = get_daily_papers()
    new_paper = paper[(paper['version'] == '1') & (paper['category'] == Category.Bioinformatics)]
    total = new_paper.shape[0]
    for index, row in tqdm(new_paper.iterrows(), total=total):
        test_paper = Paper.from_dict(row)
        print(test_paper)


if __name__ == '__main__':
    main()
