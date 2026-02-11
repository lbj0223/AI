# ============================================
# 题镜 AI - 智能错题变式系统 (云端稳定版)
# 开发者：LBJ | 核心功能：OCR识别 -> AI分析 -> 云端存储
# ============================================

import os
import argparse
import json
import requests
import psycopg2
from psycopg2.extras import Json
from PIL import Image
from openai import OpenAI
import streamlit as st
from pix2tex.cli import LatexOCR

# --- 1. 强制权限与路径重定向 (解决 PermissionError) ---
# 必须在导入模型前设置，确保所有配置指向可写的 /tmp 目录
os.environ['HOME'] = '/tmp'
os.environ['XDG_CONFIG_HOME'] = '/tmp'
os.environ['XDG_CACHE_HOME'] = '/tmp'

# ============================================
# 2. 核心配置与初始化
# ============================================

# 从 Secrets 读取 Neon 云数据库配置
db_config = st.secrets["postgres"]

# 初始化 DeepSeek 客户端
client = OpenAI(
    api_key=st.secrets["DEEPSEEK_KEY"],
    base_url="https://api.deepseek.com"
)

def ensure_model_files():
    """手动同步 AI 模型至 /tmp，绕过受限环境下的自动下载"""
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
    """
    【核心修复】使用 argparse.Namespace 解决 ValueError
    这是 pix2tex 库最兼容的参数传递方式。
    """
    ensure_model_files()
    
    # 构造标准的命名空间对象
    args = argparse.Namespace(
        config="/tmp/config.json", 
        checkpoint="/tmp/latest.pth", 
        no_cuda=True, 
        no_gui=True
    )
    return LatexOCR(args)

# 初始化 Session 状态
if 'latex_result' not in st.session_state:
    st.session_state.latex_result = ""      
if 'ai_data' not in st.session_state:
    st.session_state.ai_data = None         

# ============================================
# 3. 数据库操作 (对齐 Neon error_questions 表)
# ============================================

def get_db_connection():
    """建立带 SSL 的云端连接"""
    return psycopg2.connect(**db_config, sslmode='require')

def save_to_db(latex, ai_data):
    """保存数据至你在 Neon 创建的 error_questions 表"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # 对应 Neon SQL Editor 中的字段名
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
    """从云端获取最近 5 条历史记录"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []

# ============================================
# 4. Streamlit UI 布局
# ============================================

st.set_page_config(page_title="题镜 AI", layout="wide")
st.title("题镜 AI —— 智能错题变式系统")

# 侧边栏看板
with st.sidebar:
    st.header("🕒 云端历史看板")
    history = fetch_history()
    if history:
        for row in history:
            with st.expander(f"题目 ID: {row[0]} ({row[2].strftime('%m-%d %H:%M')})"):
                st.latex(row[1])
    else:
        st.write("暂无历史记录，快去上传第一道题吧！")

# 主界面
col1, col2 = st.columns([1, 1])

with col1:
    st.header("📸 第一步：错题录入")
    uploaded_file = st.file_uploader("上传题目图片", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, use_container_width=True)

        if st.button("开始高精度 OCR 识别"):
            with st.spinner("AI 正在还原题目 DNA... (首次运行需下载模型)"):
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 第二步：智能分析")
    if st.session_state.latex_result:
        st.subheader("题目还原 (LaTeX):")
        st.latex(st.session_state.latex_result)

        if st.button("✨ 第三步：构建变式"):
            with st.spinner("DeepSeek 正在解析..."):
                prompt = f"识别出的题目公式为：{st.session_state.latex_result}。请严格按 JSON 格式输出 card 和 exercises。"
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={'type': 'json_object'}
                )
                st.session_state.ai_data = json.loads(response.choices[0].message.content)

# 结果展示
if st.session_state.ai_data:
    st.divider()
    data = st.session_state.ai_data
    st.markdown("### 📘 知识分析")
    st.json(data['card'])
    
    if st.button("💾 存入云端错题本"):
        if save_to_db(st.session_state.latex_result, data):
            st.toast("入库成功！", icon="✅")
            st.balloons()
