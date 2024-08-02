import os.path

import streamlit as st
from tqdm import tqdm

from path import get_work_path
from util.biorxiv_fetcher import Category, get_daily_papers, Paper, YESTERDAY, download_pdf
from util.file_util import get_image, compress_folder
from util.llm_integration import conclusion

st.set_page_config(
    page_title='文献总结',
    layout='wide',
)

category_options = [category.value for category in Category]

if 'summary_history' not in st.session_state:
    st.session_state.summary_history = []

output_file = os.path.join(get_work_path(), "output", f"{YESTERDAY}-summary.md")
os.makedirs('output', exist_ok=True)

st.title("每日文献总结")
col1, col2 = st.columns([2, 3], gap='medium')

chat_container = col2.container(height=700, border=False)

with chat_container:
    for message in st.session_state.summary_history:
        icon = 'logo.png' if message['role'] != 'user' else None
        with st.chat_message(message['role']):
            st.write(message['content'])

with col1:
    st.multiselect("筛选领域", category_options, [Category.Bioinformatics], key="categories")
    st.button("生成", key="generate")

    if st.session_state.generate:
        with st.status("下载文献信息..", expanded=True) as status:
            with open(output_file, "w", encoding='utf-8') as fout:
                fout.write(f"# {YESTERDAY} BiorRxiv新发布预印本速读\t\n")
                fout.write("> 本文内容为生成式AI对文章进行总结后得到，版权归原文作者所有。总结内容可靠性无保障，请仔细鉴别并以原文为准。\t\n\n\n")

                all_paper = get_daily_papers()
                new_paper = all_paper[all_paper['version'] == '1']
                st.write("文献下载完毕")
                for cat in st.session_state.categories:
                    cat_paper = new_paper[new_paper['category'] == cat]
                    total = cat_paper.shape[0]

                    if not total == 0:
                        fout.write(f"## {cat}\t\n")

                    index = 1
                    for _, row in tqdm(cat_paper.iterrows(), total=total):
                        status.update(label=f"处理{cat}类别的文献({index}/{total})")
                        _paper = Paper.from_dict(row)

                        user_log = f"请总结文献《{_paper.title}》"
                        chat_container.chat_message("human").write(user_log)
                        st.session_state.summary_history.append({'role': 'user', 'content': user_log})

                        response = conclusion(_paper)
                        translate_result = chat_container.chat_message("ai").write_stream(response)
                        st.session_state.summary_history.append({'role': 'assistant', 'content': translate_result})
                        index += 1

                        pdf_file = download_pdf(_paper.doi)
                        first_image = get_image(pdf_file)

                        fout.write(
                            f"### {_paper.title}\t\n"
                            f"> {_paper.authors}\n"
                            f"> {_paper.author_corresponding_institution}\n\n"
                            f"[原文链接](https://doi.org/{_paper.doi})\t\n"
                            f"{translate_result}\t\n\n"
                        )

                        if first_image != "":
                            fout.write(f"![]({first_image})\t\n\n")

                    st.write(f"{cat}分类文献总结生成完毕")

            status.update(label="压缩文件...")
            compress_folder()
            st.write("文件压缩完毕")

            status.update(
                label="总结完毕",
                state="complete"
            )

    if os.path.exists(f'{YESTERDAY}-summary.zip'):
        with open(f'{YESTERDAY}-summary.zip', 'rb') as f:
            st.download_button("下载", data=f, type="primary", file_name=f'{YESTERDAY}-summary.zip', mime="application/octet-stream")
