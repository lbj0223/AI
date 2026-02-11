# ============================================
# 题镜 AI - 智能错题变式系统 (云端终极兼容版)
# ============================================

import os

# 【强制】环境路径重定向 [cite: 2026-01-31]
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


# ============================================
# 1. 核心修复：手动接管模型并兼容 Munch
# ============================================

def ensure_model_files():
    """手动同步 AI 模型至 /tmp 目录"""
    base_url = "https://github.com/lukas-blecher/LaTeX-OCR/releases/download/v0.0.1/"
    files = {
        "latest.pth": base_url + "latest.pth",
        "config.json": base_url + "config.json"
    }
    for name, url in files.items():
        path = os.path.join("/tmp", name)
        if not os.path.exists(path):
            with st.spinner(f"正在同步 AI 核心组件 {name} ..."):
                r = requests.get(url, stream=True)
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)


@st.cache_resource
def load_ocr_model():
    # 确保文件存在
    ensure_model_files()

    # 【关键改动】使用字典(Dict)代替 Namespace，解决 Munch 引起的 ValueError
    params = {
        "config": "/tmp/config.json",
        "checkpoint": "/tmp/latest.pth",
        "no_cuda": True,
        "no_gui": True
    }

    # 直接传入字典，LatexOCR 内部会自动处理
    return LatexOCR(params)


# ============================================
# 2. 数据库配置 (Neon 云端)
# ============================================

db_config = st.secrets["postgres"]


def get_db_connection():
    return psycopg2.connect(**db_config, sslmode='require')


# ... (save_to_db, fetch_history 等函数保持不变) ...

def save_to_db(latex, ai_data):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = "INSERT INTO error_questions (ocr_latex, analysis, variants) VALUES (%s, %s, %s)"
        cur.execute(query, (latex, Json(ai_data['card']), Json(ai_data['exercises'])))
        conn.commit()
        cur.close();
        conn.close()
        return True
    except Exception as e:
        st.error(f"保存失败: {e}");
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
# 3. 页面逻辑 (保持原样)
# ============================================

st.set_page_config(page_title="题镜 AI", layout="wide")
st.title("题镜 AI —— 智能错题变式系统")

with st.sidebar:
    st.header("🕒 云端历史看板")
    history = fetch_history()
    if history:
        for row in history:
            with st.expander(f"题目 ID: {row[0]} ({row[2].strftime('%m-%d %H:%M')})"):
                st.latex(row[1])
    else:
        st.write("暂无历史记录")

col1, col2 = st.columns([1, 1])
with col1:
    st.header("📸 错题录入")
    uploaded_file = st.file_uploader("上传图片", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, use_container_width=True)
        if st.button("开始识别"):
            with st.spinner("AI 正在解析公式..."):
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 智能分析")
    if 'latex_result' in st.session_state and st.session_state.latex_result:
        st.latex(st.session_state.latex_result)
        if st.button("✨ 生成变式"):
            # (DeepSeek 调用逻辑保持不变...)
            client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
            prompt = f"识别出的公式为：{st.session_state.latex_result}。请按JSON格式输出card和exercises。"
            response = client.chat.completions.create(model="deepseek-chat",
                                                      messages=[{"role": "user", "content": prompt}],
                                                      response_format={'type': 'json_object'})
            st.session_state.ai_data = json.loads(response.choices[0].message.content)

if 'ai_data' in st.session_state and st.session_state.ai_data:
    st.divider()
    if st.button("💾 存入云端错题本"):
        if save_to_db(st.session_state.latex_result, st.session_state.ai_data):
            st.toast("入库成功！", icon="✅");
            st.balloons()