import time

import streamlit as st
from tqdm import tqdm

from util.biorxiv_fetcher import Category, get_daily_papers, Paper
from util.llm_integration import conclusion

st.set_page_config(
    page_title='文献总结',
    layout='wide',
)

category_options = [category.value for category in Category]

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
    st.multiselect("筛选领域", category_options, [Category.Bioinformatics], key="categories")
    st.button("生成", key="generate")

    if st.session_state.generate:
        with st.status("下载文献信息..", expanded=True) as status:
            all_paper = get_daily_papers()
            new_paper = all_paper[all_paper['version'] == '1']
            st.write("文献下载完毕")
            for cat in st.session_state.categories:
                cat_paper = new_paper[new_paper['category'] == cat]
                total = cat_paper.shape[0]
                for index, row in tqdm(cat_paper.iterrows(), total=total):
                    status.update(label=f"处理{cat}类别的文献({index + 1}/{total})")
                    test_paper = Paper.from_dict(row)

                    user_log = f"请总结文献《{test_paper.title}》"
                    chat_container.chat_message("human").write(user_log)
                    st.session_state.summary_history.append({'role': 'user', 'content': user_log})

                    response = conclusion(test_paper)
                    translate_result = chat_container.chat_message("ai").write_stream(response)
                    st.session_state.summary_history.append({'role': 'assistant', 'content': translate_result})

                st.write(f"{cat}分类文献总结生成完毕")
            status.update(
                label="总结完毕",
                state="complete"
            )

        # st.download_button("下载", type="primary")
