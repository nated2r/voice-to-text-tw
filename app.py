import streamlit as st
import os
import yt_dlp
from groq import Groq
from pydub import AudioSegment
import math

# --- 頁面設定 ---
st.set_page_config(page_title="YT 台灣直播轉錄 (防封鎖版)", page_icon="🛡️")
st.title("🛡️ YouTube 直播轉錄神器 (V2.0)")
st.markdown("### 支援：2小時長影片 / 台語混雜 / 自動繞過 403")
st.info("💡 程式設計師-琮程 提示：V2.0 版已加入 Android 偽裝模式。若仍失敗，請使用下方的 Cookies 上傳功能。")

# --- 獲取 API Key ---
api_key = st.secrets.get("GROQ_API_KEY")
if not api_key:
    api_key = st.text_input("未偵測到內建 Key，請輸入 Groq API Key:", type="password")

# --- 進階設定：Cookies 上傳 (備用方案) ---
with st.expander("🔧 進階設定 (如果還是 403 失敗，請點這裡)"):
    st.markdown("""
    如果自動偽裝失效，請上傳你的 **cookies.txt** 來驗證身分。
    [如何取得 cookies.txt?](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpcafejbcbkfd) (請使用電腦版 Chrome 擴充功能匯出)
    """)
    cookies_file = st.file_uploader("上傳 cookies.txt (選填)", type=["txt"])

# --- 核心功能函數 ---

def download_audio(url, cookie_path=None):
    """下載 YT 影片並轉為 MP3"""
    output_filename = "temp_audio"
    if os.path.exists(f"{output_filename}.mp3"):
        os.remove(f"{output_filename}.mp3")
        
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_filename,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64',
        }],
        'quiet': True,
        'no_warnings': True,
        # --- V2.0 關鍵更新：偽裝成 Android 客戶端 ---
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'], # 優先使用 Android API 繞過封鎖
            }
        },
        # 如果有上傳 cookies 就使用，沒有就設為 None
        'cookiefile': cookie_path if cookie_path else None,
        # 額外的 Header 偽裝
        'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return f"{output_filename}.mp3"
    except Exception as e:
        st.error(f"下載失敗 (詳細錯誤): {str(e)}")
        return None

def split_audio(file_path, chunk_length_ms=600000): 
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
    with open(audio_file_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(audio_file_path, file.read()),
            model="whisper-large-v3",
            language="zh", 
            response_format="text"
        )
    return transcription

# --- 主執行邏輯 ---
url = st.text_input("請貼上 YouTube 影片網址", placeholder="https://youtu.be/...")

if st.button("🚀 開始轉錄", type="primary"):
    if not api_key:
        st.warning("請先設定 API Key！")
        st.stop()
    if not url:
        st.warning("請輸入網址！")
        st.stop()

    client = Groq(api_key=api_key)
    status_area = st.empty()
    
    # 處理 Cookies 檔案
    cookie_path = None
    if cookies_file:
        with open("cookies.txt", "wb") as f:
            f.write(cookies_file.getbuffer())
        cookie_path = "cookies.txt"
        st.toast("已載入 Cookies 憑證！", icon="🍪")

    try:
        # 1. 下載
        status_area.info("⏳ 正在下載音訊 (V2.0 Android 模式啟動中)...")
        mp3_file = download_audio(url, cookie_path)
        
        if mp3_file:
            # 2. 切割
            status_area.info("✂️ 正在處理音訊切片...")
            chunks = split_audio(mp3_file)
            
            full_transcript = ""
            total_chunks = len(chunks)
            progress_bar = st.progress(0, text="AI 轉錄中...")
            
            # 3. 轉錄
            for idx, chunk_file in enumerate(chunks):
                progress_bar.progress((idx) / total_chunks, text=f"🎙️ 正在轉錄第 {idx+1}/{total_chunks} 部分...")
                text = transcribe_with_groq(client, chunk_file)
                full_transcript += text + "\n"
                os.remove(chunk_file)
            
            progress_bar.progress(1.0, text="✅ 處理完成！")
            os.remove(mp3_file)
            
            # 4. 結果
            st.success("轉錄成功！")
            st.text_area("轉錄內容", full_transcript, height=300)
            st.download_button("📥 下載文字檔", full_transcript, file_name="transcript.txt")
            status_area.empty()
            
            # 清理
            if os.path.exists("cookies.txt"):
                os.remove("cookies.txt")

    except Exception as e:
        st.error(f"系統錯誤: {str(e)}")
