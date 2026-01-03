import streamlit as st
import os
import subprocess
import glob
from groq import Groq
import math

# --- 頁面設定 (極簡化) ---
st.set_page_config(page_title="語音轉錄服務", page_icon="📝")

# --- 核心功能 (保持 V4.1 的強大內核，隱藏在後台) ---
# 這些函數負責處理記憶體防爆與繁體中文，不需要更動

api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    st.error("系統錯誤：未設定 API Key")
    st.stop()

def save_uploaded_file(uploaded_file):
    try:
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        if file_ext == "": file_ext = ".mp3"
        temp_filename = f"input_source{file_ext}"
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return temp_filename
    except Exception:
        return None

def split_audio_ffmpeg(input_file, chunk_time=600):
    output_pattern = "chunk_%03d.mp3"
    for f in glob.glob("chunk_*.mp3"): os.remove(f)
    cmd = ["ffmpeg", "-i", input_file, "-f", "segment", "-segment_time", str(chunk_time), "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", "-reset_timestamps", "1", "-y", output_pattern]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return sorted(glob.glob("chunk_*.mp3"))
    except:
        return []

def transcribe_with_groq(client, audio_file_path):
    with open(audio_file_path, "rb") as file:
        return client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3",
            language="zh",
            prompt="以下是台灣的繁體中文逐字稿內容。請使用繁體中文 (Traditional Chinese) 進行轉錄，包含專有名詞與上下文，不要使用簡體字。",
            response_format="text"
        )

# --- UI 介面 (根據你的要求重新設計) ---

# 1. 簡潔的標題
st.title("語音轉錄服務")

# 2. 增加一點垂直間距，讓畫面不那麼擁擠
st.write("") 

# 3. 上傳區塊 (純中文標示)
uploaded_file = st.file_uploader("請上傳音訊檔案 (MP3 / M4A)", type=["mp3", "m4a", "wav"])

# 4. 執行邏輯
if uploaded_file and st.button("開始轉錄"):
    client = Groq(api_key=api_key)
    # 使用 st.spinner 取代原本複雜的文字進度條，讓畫面更乾淨
    with st.spinner('正在處理中，請稍候...'):
        try:
            # 1. 存檔
            source_file = save_uploaded_file(uploaded_file)
            
            # 2. 切割
            chunks = split_audio_ffmpeg(source_file)
            if not chunks:
                st.error("檔案處理失敗")
                st.stop()
            
            if os.path.exists(source_file):
                os.remove(source_file)
            
            # 3. 轉錄
            full_text = ""
            total = len(chunks)
            progress_bar = st.progress(0) # 簡約的進度條
            
            for i, chunk in enumerate(chunks):
                try:
                    text = transcribe_with_groq(client, chunk)
                    full_text += text + "\n"
                except:
                    full_text += ""
                
                # 更新進度條
                progress_bar.progress((i + 1) / total)
                
                if os.path.exists(chunk):
                    os.remove(chunk)
            
            # 完成後隱藏進度條，只顯示結果
            progress_bar.empty()
            
            # 顯示結果
            st.success("轉錄完成")
            st.text_area("內容預覽", full_text, height=500)
            st.download_button("下載文字檔 (.txt)", full_text, file_name="transcription.txt")

        except Exception as e:
            st.error("發生錯誤，請重新整理頁面再試")
