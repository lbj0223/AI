# ============================================
# 题镜 AI - 智能错题变式系统 (云端终极稳定版)
# ============================================

import os

# 【核心：最优先级】强制重定向家目录到可写的 /tmp
os.environ['HOME'] = '/tmp'
os.environ['XDG_CONFIG_HOME'] = '/tmp'
os.environ['XDG_CACHE_HOME'] = '/tmp'

import streamlit as st
from pix2tex.cli import LatexOCR
from PIL import Image
from openai import OpenAI
import json
import psycopg2
from psycopg2.extras import Json
import requests
import argparse


# ============================================
# 1. 模型手动下载逻辑 (解决 PermissionError)
# ============================================

def ensure_model_files():
    """手动将模型权重下载到 /tmp，绕过库自带的报错下载器"""
    base_url = "https://github.com/lukas-blecher/LaTeX-OCR/releases/download/v0.0.1/"
    files = {
        "latest.pth": base_url + "latest.pth",
        "config.json": base_url + "config.json"
    }

    for name, url in files.items():
        path = os.path.join("/tmp", name)
        if not os.path.exists(path):
            with st.spinner(f"正在手动同步 AI 核心组件 {name} ..."):
                r = requests.get(url, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)


@st.cache_resource
def load_ocr_model():
    """使用手动指定的路径加载模型"""
    # 1. 先确保文件在 /tmp 里
    ensure_model_files()

    # 2. 构造强制路径参数
    args = argparse.Namespace(
        config="/tmp/config.json",
        checkpoint="/tmp/latest.pth",
        no_cuda=True,
        no_gui=True
    )
    return LatexOCR(args)


# ============================================
# 2. 核心配置与数据库 (对齐 Neon 云端)
# ============================================

db_config = st.secrets["postgres"]  #

client = OpenAI(
    api_key=st.secrets["DEEPSEEK_KEY"],
    base_url="https://api.deepseek.com"
)


def get_db_connection():
    return psycopg2.connect(**db_config, sslmode='require')


def save_to_db(latex, ai_data):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 统一使用 error_questions 表名
        query = "INSERT INTO error_questions (ocr_latex, analysis, variants) VALUES (%s, %s, %s)"
        cur.execute(query, (latex, Json(ai_data['card']), Json(ai_data['exercises'])))
        conn.commit()
        cur.close();
        conn.close()
        return True
    except Exception as e:
        st.error(f"云端保存失败: {e}");
        return False


def fetch_history():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close();
        conn.close()
        return rows
    except Exception:
        return []


# ============================================
# 3. Streamlit UI 布局
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

# 主功能
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 错题录入")
    uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, use_container_width=True)
        if st.button("开始识别"):
            with st.spinner("AI 正在还原题目..."):
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 智能分析")
    if 'latex_result' in st.session_state and st.session_state.latex_result:
        st.latex(st.session_state.latex_result)
        if st.button("✨ 生成变式"):
            with st.spinner("DeepSeek 解析中..."):
                prompt = f"识别出的公式为：{st.session_state.latex_result}。请按JSON输出card和exercises。"
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={'type': 'json_object'}
                )
                st.session_state.ai_data = json.loads(response.choices[0].message.content)

if 'ai_data' in st.session_state and st.session_state.ai_data:
    st.divider()
    data = st.session_state.ai_data
    st.markdown("### 📘 知识分析")
    st.json(data['card'])

    if st.button("💾 存入云端错题本"):
        if save_to_db(st.session_state.latex_result, data):
            st.toast("入库成功！", icon="✅")
            st.balloons()