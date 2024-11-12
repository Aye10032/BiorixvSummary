import calendar
import os
import random
from datetime import datetime

import pandas as pd
import streamlit as st
import requests
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from openai import BadRequestError
from pandas import DataFrame
from pydantic import FilePath, Field, BaseModel
from tqdm import tqdm
from wordcloud import WordCloud

from util.biorxiv_fetcher import USER_AGENT, CONTENT_ENDPOINT
from util.decorator import retry

KEYWORD_SYSTEM = """
I will provide you with the abstract of an academic paper. 
Please analyze the abstract and extract between 3 to 7 key terms that best represent the main topics, concepts, or methods discussed in the paper. 
These terms should be highly relevant to the paper's content, unique enough to capture its focus, and commonly understood in academic or professional contexts. 
Only respond with the keywords as a comma-separated list, without any additional commentary.

===========================
**Example Abstract:** 
Molecular diagnostics for the rapid identification of infectious, virulent, and pathogenic organisms are key to health and global security. 
Such methods rely on the identification and detection of signatures possessed by the organism. 
In this work, we outline a computational algorithm, GenomicSign, to determine unique and amplifiable genomic signatures of a set of target sequences against a background set of non-target sequences. 
The set of target sequences might comprise variants of a pathogen of interest, say SARS-CoV2 virus. 
Unique k-mers of the consensus target sequence for a range of k-values are determined, and the threshold k-value yielding a sharp transition in the number of unique k-mers is identified as kopt. 
Corresponding unique k-mers for k ≥ kopt are compared against the set of non-target sequences to identify targetspecific unique k-mers. 
A pair of proximal such k-mers could enclose a potential amplicon.
Primers to such pairs are designed and scored using a custom scheme to rank the potential amplicons. 
The top-ranked resulting amplicons are candidates for unique and amplifiable genomic signatures. 
The entire workflow is demonstrated using a case study with the SARS-CoV2 omicron genome. 
A case study distinguishing the SARS-CoV2 omicron target strain against non-target other SARS-CoV2 variants is performed to illustrate the workflow.

**Example Output:**
['Infectious organisms', 'genomic signatures', 'pathogen detection', 'molecular diagnostics', 'DNA amplification', 'k-mer analysis', 'DNA fingerprinting', 'k-mer island discovery', 'primer design']
===========================

{format_instructions}
"""

KEYWORD_QUESTION = """
Here is the abstract of a research paper. Please extract 3 to 7 keywords based on its core topics and methods.

## Abstract
{abstract}
"""


class KeywordResponse(BaseModel):
    keywords: list[str] = Field(description='Keywords list of the paper.')


def get_month_start_end(month: int) -> tuple[str, str]:
    year = datetime.now().year
    first_day = f"{year}-{month:02d}-01"
    last_day = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}"
    return first_day, last_day


@retry(delay=random.uniform(2.0, 5.0))
def download_info(month: int, start: int = 0) -> tuple[int, DataFrame]:
    first_day, last_day = get_month_start_end(month)

    url = f"{CONTENT_ENDPOINT}/{first_day}/{last_day}/{start}/json"
    payload = {}
    headers = {'User-Agent': USER_AGENT}

    response = requests.request("GET", url, headers=headers, data=payload).json()
    message: dict = response['messages'][0]

    total = int(message['total'])
    if message['status'] != "ok":
        raise Exception("下载信息失败")

    return total, DataFrame(response['collection'])


def get_month_data(month: int, csv_path: FilePath) -> None:
    if os.path.exists(csv_path):
        os.remove(csv_path)
        logger.warning('检测到已经存在文件，已删除')

    total, _ = download_info(month)
    logger.info(f'总共 {total} 篇文献，开始下载...')

    for start in tqdm(range(0, total, 100)):
        _, df = download_info(month, start)
        df.to_csv(csv_path, index=False, mode='a', header=not os.path.exists(csv_path))

    logger.info(f'结果已保存至 {csv_path}')


def clear_data(raw_path: FilePath, clean_path: FilePath) -> DataFrame:
    raw_data = pd.read_csv(raw_path)
    clean_data = raw_data.drop_duplicates(
        subset=['doi']
    ).drop(
        columns=[
            'authors', 'author_corresponding',
            'author_corresponding_institution',
            'version', 'type',
            'license', 'jatsxml',
            'published', 'server'
        ]
    )

    clean_data.to_csv(clean_path, index=False)

    return clean_data


def get_key_words(paper_infos: DataFrame, result_path: FilePath) -> None:
    @retry(delay=random.uniform(2.0, 5.0))
    def ask_llm(_abstract: str):
        llm = ChatOpenAI(
            model_name="glm-4-flash",
            openai_api_base='https://open.bigmodel.cn/api/paas/v4',
            temperature=0.1,
            openai_api_key=st.secrets['gml_key'],
        )

        parser = PydanticOutputParser(pydantic_object=KeywordResponse)

        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(KEYWORD_SYSTEM),
            HumanMessagePromptTemplate.from_template(KEYWORD_QUESTION)
        ])

        prompt_and_model = prompt | llm | parser

        try:
            return prompt_and_model.invoke({'abstract': _abstract, 'format_instructions': parser.get_format_instructions()})
        except BadRequestError:
            llm_gpt = ChatOpenAI(
                model_name="gpt-4o-mini",
                temperature=0.1,
                openai_api_key=st.secrets['gpt_key'],
            )
            prompt_and_model = prompt | llm_gpt | parser
            logger.warning('check to gpt 40 mini')

            return prompt_and_model.invoke({'abstract': _abstract, 'format_instructions': parser.get_format_instructions()})

    if os.path.exists(result_path):
        output_df = pd.read_csv(result_path)
        logger.info(f'load from {result_path}, total: {len(output_df)}')
    else:
        output_df = paper_infos.copy()
        output_df['keywords'] = pd.NA
        logger.info(f'load from dataframe, total: {len(output_df)}')

    for index, row in tqdm(output_df.iterrows(), total=len(output_df)):
        if not pd.isna(row.keywords):
            continue

        abstract = row['abstract']

        result = ask_llm(abstract)
        output_df.at[index, 'keywords'] = result.keywords
        output_df.at[index, 'abstract'] = pd.NA

        if index % 10 == 0:
            output_df.to_csv(result_path, index=False)

    output_df.to_csv(result_path, index=False)


def draw_wordcloud(result_path: FilePath, image_path: FilePath, month: int):
    result_data = pd.read_csv(result_path)
    all_keywords = result_data['keywords'].dropna().apply(eval).explode()
    word_freq = all_keywords.value_counts()
    filtered_word_freq = word_freq[word_freq > 1]

    wordcloud: WordCloud = WordCloud(
        width=1920,
        height=1080,
        background_color='white'
    ).generate_from_frequencies(filtered_word_freq)

    image = wordcloud.to_image()
    image.save(os.path.join(image_path, f'conclusion_{month}.png'), 'png')

    print(filtered_word_freq)

    for category in tqdm(result_data['category'].unique()):
        sub_data = result_data[result_data['category'] == category]
        sub_keywords = sub_data['keywords'].dropna().apply(eval).explode()
        sub_word_freq = sub_keywords.value_counts()

        sub_wordcloud: WordCloud = WordCloud(
            width=1920,
            height=1080,
            max_words=100,
            background_color='white'
        ).generate_from_frequencies(sub_word_freq)

        image = sub_wordcloud.to_image()
        image.save(os.path.join(image_path, f'{category}_{month}.png'), 'png')


def main() -> None:
    month = 10
    raw_path = os.path.join('conclusion', f'paper_{month}.csv')
    clean_path = os.path.join('conclusion', f'clean_{month}.csv')
    result_path = os.path.join('conclusion', f'result_{month}.csv')
    image_path = os.path.join('conclusion', 'image')

    os.makedirs(image_path, exist_ok=True)
    # get_month_data(month, raw_path)
    # data = clear_data(raw_path, clean_path)
    # get_key_words(data, result_path)
    draw_wordcloud(result_path, image_path, month)


if __name__ == '__main__':
    main()
