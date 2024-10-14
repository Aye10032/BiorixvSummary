import streamlit as st

from operator import itemgetter

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from util.biorxiv_fetcher import Paper

SYSTEM_PROMPT = """You are an expert research assistant specializing in summarizing academic papers.
Your task is to provide a concise and comprehensive summary of a given academic paper."""

ASK_PROMPT = """下面是文献的相关信息：
\n==================\n{info}\n====================\n
请用中文以简洁的语言给出的文献内容进行总结，务必包含文献真正关键的信息。尽可能不超过400字，若内容非常多，不超过600字。
首先用一到两段概括全文的主要内容，以“来自XXX的这项研究工作...”或“来自XXX的研究团队在这篇文章中...”或“来自XXX的研究人员提出了...”类似的句子开头。这部分不用包含对与研究意义的概括。
在最后，另起一行用一句话总结这篇文献的意义，以“这项研究...”开头。"""


def load_gpt() -> ChatOpenAI:
    llm = ChatOpenAI(
        model_name="glm-4-flash",
        openai_api_base='https://open.bigmodel.cn/api/paas/v4/',
        temperature=0.6,
        openai_api_key=st.secrets['gml_key'],
        streaming=True
    )
    return llm


def format_paper(paper: Paper) -> str:
    formatted_str = (
        f"Title: {paper.title}\n"
        f"Institution: {paper.author_corresponding_institution}\n"
        f"# Abstract\n {paper.abstract}"
    )

    if paper.more_graph:
        for title, text in paper.more_graph.items():
            formatted_str += f"\n\n# {title}\n{text}"

    return formatted_str


def conclusion(paper: Paper):
    formatter = itemgetter("paper") | RunnableLambda(format_paper)

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=SYSTEM_PROMPT),
        ('human', ASK_PROMPT)
    ])

    llm = load_gpt()

    chain = {'info': formatter} | prompt | llm

    result = chain.stream({'paper': paper})

    return result
