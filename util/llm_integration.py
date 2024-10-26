import streamlit as st

from operator import itemgetter

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from util.biorxiv_fetcher import Paper

SYSTEM_PROMPT = """你是一名科研助理，你的任务是对于用户给出的科研文献内容进行精炼总结，总结时需要遵从以下格式：
你给出的总结总共分为两段，600字以内。
第一段以以“来自XXX的这项研究工作...”或“来自XXX的研究团队在这篇文章中...”或“来自XXX的研究人员提出了...”类似的句子开头。这一段的总结内容包括文章的创新点、主要内容、取得的主要成果、作者认为未来要做的工作（如果有）。
第二段以“这项研究...”开头，用一句话总结一下这篇文章的意义。"""

ASK_PROMPT = """下面是文献的相关信息：
\n==================\n{info}\n====================\n
请用中文以简洁的语言给出的文献内容进行总结，，符合要求的格式，务必包含文献真正关键的信息。"""


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
        f"**Title**: {paper.title}\n"
        f"**Institution**: {paper.author_corresponding_institution}\n"
        f"# Abstract\r\n {paper.abstract}"
    )

    if paper.more_graph:
        for title, text in paper.more_graph.items():
            formatted_str += f"\r\n# {title}\r\n{text}"

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
