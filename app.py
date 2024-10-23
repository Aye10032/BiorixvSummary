import os.path
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import streamlit as st
from tqdm import tqdm

from path import get_work_path
from util.biorxiv_fetcher import Category, get_daily_papers, Paper, download_pdf, MAIN_LIST
from util.file_util import get_image, compress_folder, DocData, write_to_docx
from util.grobid_util import parse_pdf, extract_paragraphs
from util.llm_integration import conclusion

st.set_page_config(
    page_title='文献总结',
    layout='wide',
)

os.environ["LANGCHAIN_TRACING_V2"] = 'true'
os.environ["LANGCHAIN_API_KEY"] = st.secrets['langsmith_api']
os.environ["LANGCHAIN_PROJECT"] = 'BioSummary'

category_options = [category.value for category in Category]
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

if 'summary_history' not in st.session_state:
    st.session_state.summary_history = []

st.title("每日文献总结")
col1, col2 = st.columns([2, 3], gap='medium')

chat_container = col2.container(height=700, border=False)

with chat_container:
    for message in st.session_state.summary_history:
        icon = 'logo.png' if message['role'] != 'user' else None
        with st.chat_message(message['role']):
            st.write(message['content'])

with col1:
    st.toggle("全部分类", key="all_category")
    st.multiselect("筛选领域", category_options, [Category.Bioinformatics], key="categories", disabled=st.session_state.all_category)
    st.button("生成", key="generate")

    if st.session_state.generate:
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        with st.status("下载文献信息..", expanded=True) as status:
            all_paper = get_daily_papers(yesterday)
            new_paper = all_paper[all_paper['version'] == '1'].sort_values(by='category')
            total = new_paper.shape[0]

            if total == 0:
                st.warning('昨日没有新发布的论文')
                st.stop()

            st.write("文献下载完毕")
            if st.session_state.all_category:
                category_list = all_paper['category'].unique().tolist()
            else:
                category_list = st.session_state.categories

            for cat in category_list:
                cat_paper = new_paper[new_paper['category'] == cat]
                total = cat_paper.shape[0]

                if total == 0:
                    continue

                base_path = os.path.join(get_work_path(), 'tmp', cat)

                output_file = os.path.join(
                    get_work_path(),
                    f'{yesterday}-summary',
                    f"{yesterday} BiorRxiv预印本速读【{cat.title()}】.docx"
                ) if cat not in MAIN_LIST else os.path.join(
                    get_work_path(),
                    f'{yesterday}-summary',
                    'main',
                    f"{yesterday} BiorRxiv预印本速读【{cat.title()}】.docx"
                )

                os.makedirs(os.path.dirname(output_file), exist_ok=True)

                if os.path.exists(output_file):
                    st.write(f"{cat}分类文献总结生成完毕")
                    continue

                index = 1
                paper_data = []
                for _, row in tqdm(cat_paper.iterrows(), total=total):
                    status.update(label=f"处理{cat}类别的文献({index}/{total})")
                    _paper = Paper.from_dict(row)

                    pdf_file = download_pdf(base_path, _paper.doi)

                    with ThreadPoolExecutor() as executor:
                        future_first_image = executor.submit(get_image, pdf_file)
                        future_parsed_pdf = executor.submit(parse_pdf, pdf_file)

                        parsed_pdf = future_parsed_pdf.result()
                        future_more_paragraphs = executor.submit(extract_paragraphs, parsed_pdf)

                        first_image = future_first_image.result()
                        more_paragraphs = future_more_paragraphs.result()

                    _paper.more_graph = more_paragraphs

                    user_log = f"请总结文献《{_paper.title}》"
                    chat_container.chat_message("human").write(user_log)
                    st.session_state.summary_history.append({'role': 'user', 'content': user_log})

                    response = conclusion(_paper)
                    conclusion_result = chat_container.chat_message("ai").write_stream(response)
                    st.session_state.summary_history.append({'role': 'assistant', 'content': conclusion_result})
                    index += 1

                    author_list = _paper.authors.split('; ')
                    author_str = "; ".join(author_list[:2]+['et.al.'] if len(author_list) > 2 else author_list)
                    author_corresponding = "; ".join([
                        f"{a}*"
                        for a in _paper.author_corresponding.split('; ')
                    ])
                    paper_data.append(DocData(
                        _paper.title,
                        f"{author_str}, {author_corresponding}",
                        _paper.author_corresponding_institution,
                        _paper.doi,
                        conclusion_result,
                        first_image
                    ))

                status.update(label="保存结果至docx文件...")
                write_to_docx(paper_data, output_file)
                st.write(f"{cat}分类文献总结生成完毕")

            status.update(label="压缩文件...")
            compress_folder(yesterday)
            shutil.rmtree('tmp')
            st.write("文件压缩完毕")

            status.update(
                label="总结完毕",
                state="complete"
            )

    if os.path.exists(f'{yesterday}-summary.zip'):
        with open(f'{yesterday}-summary.zip', 'rb') as f:
            st.download_button("下载", data=f, type="primary", file_name=f'{yesterday}-summary.zip', mime="application/octet-stream")
