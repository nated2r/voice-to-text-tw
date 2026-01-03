import streamlit as st
import os
import yt_dlp
from groq import Groq
from pydub import AudioSegment
import math

# --- 頁面設定 ---
st.set_page_config(page_title="YT 台灣直播轉錄 (Groq版)", page_icon="🎙️")
st.title("🎙️ YouTube 直播轉錄神器")
st.markdown("### 支援：2小時長影片 / 台語混雜 / 不公開影片")
st.info("💡 程式設計師-琮程 提示：首次啟動可能需要幾分鐘安裝環境。")

# --- 獲取 API Key ---
# 優先從 Streamlit Secrets 讀取，如果沒有則顯示輸入框
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    api_key = st.text_input("未偵測到內建 Key，請輸入 Groq API Key:", type="password")

# --- 核心功能函數 ---

def download_audio(url):
    """下載 YT 影片並轉為 MP3 (低位元率以節省體積)"""
    output_filename = "temp_audio"
    # 清理舊檔
    if os.path.exists(f"{output_filename}.mp3"):
        os.remove(f"{output_filename}.mp3")
        
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_filename,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64', # 64k 對語音辨識已足夠，且處理速度更快
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f"{output_filename}.mp3"
    except Exception as e:
        st.error(f"下載失敗，請確認連結是否有效: {e}")
        return None

def split_audio(file_path, chunk_length_ms=600000): # 10分鐘一段
    """將音檔切割成小片段以符合 Groq 25MB 限制"""
    audio = AudioSegment.from_mp3(file_path)
    chunks = []
    duration_ms = len(audio)
    total_chunks = math.ceil(duration_ms / chunk_length_ms)
    
    progress_text = "正在切割音檔..."
    my_bar = st.progress(0, text=progress_text)

    for i in range(total_chunks):
        start_time = i * chunk_length_ms
        end_time = min((i + 1) * chunk_length_ms, duration_ms)
        chunk = audio[start_time:end_time]
        chunk_name = f"chunk_{i}.mp3"
        chunk.export(chunk_name, format="mp3")
        chunks.append(chunk_name)
        my_bar.progress((i + 1) / total_chunks, text=f"正在切割第 {i+1}/{total_chunks} 段")
    
    my_bar.empty()
    return chunks

def transcribe_with_groq(client, audio_file_path):
    """呼叫 Groq API"""
    with open(audio_file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3",
            language="zh", # 強制辨識為中文 (包含台語上下文)
            response_format="text"
        )
    return transcription

# --- 主執行邏輯 ---
url = st.text_input("請貼上 YouTube 影片網址 (支援不公開連結)", placeholder="https://youtu.be/...")

if st.button("🚀 開始轉錄", type="primary"):
    if not api_key:
        st.warning("請先輸入 API Key！")
        st.stop()
        
    if not url:
        st.warning("請輸入影片網址！")
        st.stop()

    client = Groq(api_key=api_key)
    status_area = st.empty()
    
    try:
        # 1. 下載
        status_area.info("⏳ 正在下載音訊 (長影片約需 1-3 分鐘)...")
        mp3_file = download_audio(url)
        
        if mp3_file:
            # 2. 切割
            status_area.info("✂️ 正在處理音訊切片...")
            chunks = split_audio(mp3_file)
            
            full_transcript = ""
            total_chunks = len(chunks)
            progress_bar = st.progress(0, text="AI 轉錄中...")
            
            # 3. 轉錄
            for idx, chunk_file in enumerate(chunks):
                progress_bar.progress((idx) / total_chunks, text=f"🎙️ 正在轉錄第 {idx+1}/{total_chunks} 部分 (Groq V3)...")
                text = transcribe_with_groq(client, chunk_file)
                full_transcript += text + "\n"
                os.remove(chunk_file) # 處理完馬上刪除釋放空間
            
            progress_bar.progress(1.0, text="✅ 處理完成！")
            os.remove(mp3_file) # 刪除原始檔
            
            # 4. 結果顯示
            st.success("轉錄成功！")
            st.text_area("轉錄內容預覽", full_transcript, height=300)
            st.download_button(
                label="📥 下載完整文字檔 (.txt)",
                data=full_transcript,
                file_name="transcript.txt",
                mime="text/plain"
            )
            status_area.empty()

    except Exception as e:
        st.error(f"發生未預期的錯誤: {str(e)}")