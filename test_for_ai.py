# ============================================
# 题镜 AI - 智能错题变式系统 (云端终极稳定版)
# 开发者：LBJ | 核心功能：OCR识别 -> AI分析 -> 云端存储
# ============================================

import os
# 【优先级最高】强制权限重定向，解决 PermissionError
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
# 1. 核心修复：构造“双向兼容”配置类
# ============================================

class LatexConfig(dict):
    """
    【计科专业级方案】
    继承 dict 以兼容 Munch.update (解决 ValueError)
    支持 __getattr__ 以支持点符号访问 .config (解决 AttributeError)
    """
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(f"'LatexConfig' object has no attribute '{name}'")

def ensure_model_files():
    """手动同步 AI 模型至 /tmp，修复 404 导致的 ValueError"""
    # 官方 Release 的正确链接
    base_url = "https://github.com/lukas-blecher/LaTeX-OCR/releases/download/v0.0.1/"
    # 官方配置文件的链接
    config_url = "https://raw.githubusercontent.com/lukas-blecher/LaTeX-OCR/main/pix2tex/model/settings/config.yaml"
    
    files = {
        "weights.pth": base_url + "weights.pth",
        "image_resizer.pth": base_url + "image_resizer.pth",
        "config.yaml": config_url
    }
    
    for name, url in files.items():
        path = os.path.join("/tmp", name)
        if not os.path.exists(path):
            with st.spinner(f"正在同步 AI 核心组件 {name} ..."):
                r = requests.get(url, stream=True)
                if r.status_code == 200:
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    st.error(f"下载失败 {name}: HTTP {r.status_code}")

@st.cache_resource
def load_ocr_model():
    # 1. 确保所有文件已在 /tmp
    ensure_model_files()
    
    # 2. 构造兼容性对象，明确指向 /tmp 下的文件
    params = LatexConfig({
        "config": "/tmp/config.yaml", 
        "checkpoint": "/tmp/weights.pth",
        "resizer": "/tmp/image_resizer.pth",
        "no_cuda": True, 
        "no_gui": True
    })
    
    # 3. 传入 LatexOCR，彻底打通权限与逻辑
    return LatexOCR(params)

# ============================================
# 2. 数据库逻辑 (对齐 Neon 云端)
# ============================================

db_config = st.secrets["postgres"]

def get_db_connection():
    return psycopg2.connect(**db_config, sslmode='require')

def save_to_db(latex, ai_data):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = "INSERT INTO error_questions (ocr_latex, analysis, variants) VALUES (%s, %s, %s)"
        cur.execute(query, (latex, Json(ai_data['card']), Json(ai_data['exercises'])))
        conn.commit()
        cur.close(); conn.close()
        return True
    except Exception as e:
        st.error(f"保存失败: {e}"); return False

def fetch_history():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, ocr_latex, created_at FROM error_questions ORDER BY created_at DESC LIMIT 5")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return rows
    except Exception: return []

# ============================================
# 3. Streamlit UI 布局
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
    st.header("📸 第一步：错题录入")
    uploaded_file = st.file_uploader("上传题目图片", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, use_container_width=True)
        if st.button("开始高精度 OCR 识别"):
            with st.spinner("AI 正在解析公式... (首次运行需 1 分钟)"):
                model = load_ocr_model()
                st.session_state.latex_result = model(img)
                st.rerun()

with col2:
    st.header("🧠 第二步：智能分析")
    if 'latex_result' in st.session_state and st.session_state.latex_result:
        st.latex(st.session_state.latex_result)
        if st.button("✨ 第三步：构建变式"):
            with st.spinner("DeepSeek 正在解析..."):
                client = OpenAI(api_key=st.secrets["DEEPSEEK_KEY"], base_url="https://api.deepseek.com")
                prompt = f"识别出的公式为：{st.session_state.latex_result}。请按 JSON 输出 card 和 exercises。"
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={'type': 'json_object'}
                )
                st.session_state.ai_data = json.loads(response.choices[0].message.content)

if 'ai_data' in st.session_state and st.session_state.ai_data:
    st.divider()
    if st.button("💾 存入云端 AI 错题本"):
        if save_to_db(st.session_state.latex_result, st.session_state.ai_data):
            st.toast("入库成功！", icon="✅"); st.balloons()
