# ============================================
# 题镜 AI - 智能错题变式系统 (云端稳定版)
# ============================================

import streamlit as st
from pix2tex.cli import LatexOCR
from PIL import Image
from openai import OpenAI
import json
import psycopg2
from psycopg2.extras import Json
import os

# --- 解决 PermissionError 的关键配置 ---
# 强制让 AI 权重下载到可写的 /tmp 目录
os.environ['XDG_CONFIG_HOME'] = '/tmp'

# ============================================
# 1. 核心配置与数据库初始化
# ============================================

db_config = st.secrets["postgres"]
DEEPSEEK_KEY = st.secrets["DEEPSEEK_KEY"]

client = OpenAI(
    api_key=DEEPSEEK_KEY,
    base_url="https://api.deepseek.com"
)


# 使用缓存加载模型，防止重复下载和内存溢出
@st.cache_resource
def load_ocr_model():
    return LatexOCR()


# 初始化会话状态
if 'latex_result' not in st.session_state:
    st.session_state.latex_result = ""
if 'ai_data' not in st.session_state:
    st.session_state.ai_data = None


# ============================================
# 2. 数据库操作函数 (全部对齐 Neon 云端)
# ============================================

def get_db_connection():
    return psycopg2.connect(**db_config, sslmode='require')


def save_to_db(latex, ai_data):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 确保表名与你在 Neon SQL Editor 中创建的一致
        query = """
        INSERT INTO error_questions (ocr_latex, analysis, variants)
        VALUES (%s, %s, %s)
        """
        cur.execute(query, (
            latex,
            Json(ai_data['card']),
            Json(ai_data['exercises'])
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"云端同步失败：{e}")
        return False


def fetch_history():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        return []


def clear_history():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM error_questions")
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"清空失败：{e}")
        return False


# ============================================
# 3. 界面布局
# ============================================

st.set_page_config(page_title="题镜 AI", layout="wide")
st.title("题镜 AI —— 智能错题变式系统")

# 侧边栏
with st.sidebar:
    st.header("🕒 云端历史看板")
    history = fetch_history()
    if history:
        for row in history:
            with st.expander(f"题目 ID: {row[0]} ({row[2].strftime('%m-%d %H:%M')})"):
                st.latex(row[1])
    else:
        st.write("暂无历史记录")

    st.divider()
    if st.button("🗑️ 清空记录"):
        if clear_history():
            st.rerun()

# 主功能区
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 错题录入")
    uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, use_container_width=True)

        if st.button("开始识别"):
            with st.spinner("正在还原题目..."):
                # 使用缓存的模型
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 智能分析")
    if st.session_state.latex_result:
        st.latex(st.session_state.latex_result)

        if st.button("✨ 生成变式"):
            with st.spinner("AI 解析中..."):
                prompt = f"识别出的题目公式为：{st.session_state.latex_result}。请按JSON格式输出考点card和exercises变式练习。"
                try:
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={'type': 'json_object'}
                    )
                    st.session_state.ai_data = json.loads(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"分析失败：{e}")

if st.session_state.ai_data:
    st.divider()
    data = st.session_state.ai_data
    st.markdown("### 📘 知识点分析")
    st.json(data['card'])

    st.markdown("### ✍️ 变式练习")
    for ex in data['exercises']:
        st.write(f"**{ex['type']}**")
        st.write(ex['q'])
        with st.expander("查看解析"):
            st.success(ex['a'])

    if st.button("💾 存入云端错题本"):
        if save_to_db(st.session_state.latex_result, data):
            st.toast("入库成功！", icon="✅")
            st.balloons()