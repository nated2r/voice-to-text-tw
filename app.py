import streamlit as st
import os
import yt_dlp
from groq import Groq
from pydub import AudioSegment
import math

# --- 頁面設定 ---
st.set_page_config(page_title="轉錄神器 V3 (上傳版)", page_icon="📂")
st.title("🎙️ 逐字稿轉錄神器 (檔案上傳版)")
st.markdown("### 支援：MP3/M4A 音檔直接上傳 (推薦使用)")

# --- 1. 獲取 API Key ---
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    st.error("❌ 錯誤：未設定 GROQ_API_KEY，請至後台 Secrets 設定。")
    st.stop()

# --- 核心功能函數 ---

def save_uploaded_file(uploaded_file):
    """儲存使用者上傳的檔案到暫存區"""
    try:
        # 取得副檔名
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        temp_filename = f"temp_input{file_ext}"
        
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return temp_filename
    except Exception as e:
        st.error(f"檔案儲存失敗: {e}")
        return None

def convert_to_mp3(input_file):
    """將任意音訊轉為標準 MP3 (16kHz 單聲道，最適合 Whisper)"""
    output_filename = "converted_audio.mp3"
    audio = AudioSegment.from_file(input_file)
    # 轉成單聲道、16000Hz 以節省 Groq 傳輸流量並加快速度
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_filename, format="mp3", bitrate="64k")
    return output_filename

def split_audio(file_path, chunk_length_ms=600000): 
    # 10 分鐘切一段 (600,000 ms)
    audio = AudioSegment.from_mp3(file_path)
    chunks = []
    duration_ms = len(audio)
    total_chunks = math.ceil(duration_ms / chunk_length_ms)
    
    for i in range(total_chunks):
        start_time = i * chunk_length_ms
        end_time = min((i + 1) * chunk_length_ms, duration_ms)
        chunk = audio[start_time:end_time]
        chunk_name = f"chunk_{i}.mp3"
        chunk.export(chunk_name, format="mp3")
        chunks.append(chunk_name)
    return chunks

def transcribe_with_groq(client, audio_file_path):
    with open(audio_file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3",
            language="zh", 
            response_format="text"
        )
    return transcription

# --- 主介面 ---

st.info("💡 提示：請上傳 MP3 或 M4A 檔案。雖然我們解除了 200MB 限制，但建議檔案不要超過 500MB。")

# 這裡就是你要的「檔案上傳按鈕」
uploaded_file = st.file_uploader("請選擇音訊檔案", type=["mp3", "m4a", "wav"])

if uploaded_file and st.button("🚀 開始轉錄"):
    client = Groq(api_key=api_key)
    status = st.empty()
    progress = st.progress(0, text="準備中...")
    
    try:
        # 1. 存檔
        status.info("⏳ 1/4 正在讀取檔案...")
        temp_file = save_uploaded_file(uploaded_file)
        
        # 2. 轉檔 (標準化)
        status.info("⚙️ 2/4 正在最佳化音訊格式...")
        mp3_file = convert_to_mp3(temp_file)
        os.remove(temp_file) # 刪掉原始檔省空間
        
        # 3. 切割
        status.info("✂️ 3/4 正在切割音訊...")
        chunks = split_audio(mp3_file)
        
        # 4. 轉錄
        full_text = ""
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            status.info(f"🎙️ 4/4 AI 正在聽寫中... (進度 {i+1}/{total})")
            progress.progress((i)/total)
            text = transcribe_with_groq(client, chunk)
            full_text += text + "\n"
            os.remove(chunk) # 處理完馬上刪，省空間
        
        progress.progress(1.0)
        status.success("🎉 轉錄完成！")
        
        # 顯示結果
        st.text_area("轉錄逐字稿", full_text, height=400)
        st.download_button("📥 下載 .txt 文字檔", full_text, file_name="transcript.txt")
        
        # 最後清理
        if os.path.exists(mp3_file):
            os.remove(mp3_file)

    except Exception as e:
        st.error(f"發生錯誤: {e}")
