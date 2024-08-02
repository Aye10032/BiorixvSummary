import streamlit as st

from operator import itemgetter

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from util.biorxiv_fetcher import Paper

SYSTEM_PROMPT = """You are an expert research assistant specializing in summarizing academic papers.
Your task is to provide a concise and comprehensive summary of a given academic paper."""

ASK_PROMPT = """下面是文献的相关信息：\n{info}\n\n请用中文以尽可能简洁的语言给出的文献内容进行总结。"""


def load_gpt() -> ChatOpenAI:
    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=0.6,
        openai_api_key=st.secrets['gpt_key'],
        streaming=True
    )
    return llm


def format_paper(paper: Paper) -> str:
    formatted_str = (
        f"Title: {paper.title}\n"
        f"Authors: {paper.authors}\n"
        f"Institution: {paper.author_corresponding_institution}\n"
        f"Abstract: {paper.abstract}"
    )

    return formatted_str


def conclusion(paper: Paper):
    formatter = itemgetter("paper") | RunnableLambda(format_paper)

    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=SYSTEM_PROMPT),
        ('human', ASK_PROMPT)
    ])

    llm = load_gpt()

    chain = {'info': formatter} | prompt | llm

    result = chain.invoke({'paper': paper})

    return result
