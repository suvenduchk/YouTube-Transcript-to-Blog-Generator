import streamlit as st
from dotenv import load_dotenv
import os
import re
import requests

load_dotenv()

def get_transcript_with_ytdlp(video_url):
    """Get transcript using yt-dlp Python module"""
    try:
        import yt_dlp
        
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            subtitle_url = None
            for lang in ['en', 'en-US', 'en-GB']:
                if lang in subtitles:
                    for sub in subtitles[lang]:
                        if sub.get('ext') == 'vtt':
                            subtitle_url = sub.get('url')
                            break
                    if subtitle_url:
                        break
                        
                if not subtitle_url and lang in automatic_captions:
                    for sub in automatic_captions[lang]:
                        if sub.get('ext') == 'vtt':
                            subtitle_url = sub.get('url')
                            break
                    if subtitle_url:
                        break
            
            if subtitle_url:
                import urllib.request
                with urllib.request.urlopen(subtitle_url) as response:
                    content = response.read().decode('utf-8')
                
                lines = content.split('\n')
                transcript_text = []
                
                for line in lines:
                    line = line.strip()
                    if (not line or 
                        line.startswith('WEBVTT') or 
                        '-->' in line or 
                        line.isdigit() or
                        re.match(r'^\d{2}:\d{2}:\d{2}', line) or
                        line.startswith('<') or
                        'NOTE' in line):
                        continue
                    transcript_text.append(line)
                
                full_text = ' '.join(transcript_text)
                return full_text, len(transcript_text), None
            else:
                return None, 0, "No English subtitles found"
                
    except ImportError:
        return None, 0, "yt-dlp module not installed. Use: pip install yt-dlp"
    except Exception as e:
        return None, 0, f"Error with yt-dlp: {str(e)}"

def generate_blog_with_groq(transcript_text, video_title):
    """Generate blog using direct Groq API call"""
    try:
        from groq import Groq
        
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Limit transcript to avoid token limits
        limited_transcript = transcript_text[:5000] if len(transcript_text) > 5000 else transcript_text
        
        prompt = f"""
You are a blog writer who creates content STRICTLY from video transcripts. 

TRANSCRIPT FROM VIDEO "{video_title}":
{limited_transcript}

INSTRUCTIONS:
1. Create a blog post using ONLY the information from the transcript above
2. DO NOT add external knowledge or information not in the transcript
3. Use the actual content, topics, and examples mentioned in the transcript
4. Create a relevant title based on what's discussed in the transcript
5. Structure: Title, Introduction, Main Content (2-3 sections), Conclusion
6. Include specific quotes or points from the transcript
7. Stay true to the actual video content

Generate a complete blog post now:
"""

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a blog writer who creates content strictly from provided transcripts without adding external information."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error generating blog: {str(e)}"

def main():
    st.set_page_config(
        page_title="YouTube Transcript to Blog",
        page_icon="📝",
        layout="wide"
    )
    
    st.title("📝 YouTube Transcript to Blog Generator")
    st.markdown("**Extracts video transcripts and creates blogs from transcript content ONLY**")
    
    # Check API key
    if not os.getenv("GROQ_API_KEY"):
        st.error("❌ GROQ_API_KEY not found! Add it to your .env file")
        return
    
    st.success("✅ Groq API key loaded")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("🎥 YouTube Video Input")
        
        youtube_url = st.text_input(
            "Enter YouTube URL:",
            placeholder="https://www.youtube.com/watch?v=VIDEO_ID"
        )
        
        video_title = st.text_input(
            "Video Title (optional):",
            placeholder="Enter video title"
        )
        
        if youtube_url and st.button("🚀 Extract & Generate Blog", type="primary"):
            
            # Step 1: Extract transcript
            with st.spinner("Extracting transcript..."):
                transcript_text, transcript_length, error_msg = get_transcript_with_ytdlp(youtube_url)
            
            if transcript_text:
                st.success(f"✅ Transcript extracted! ({transcript_length} segments)")
                
                # Show transcript preview
                with st.expander("📜 View Extracted Transcript"):
                    st.text_area(
                        "Transcript:",
                        transcript_text[:2000] + "..." if len(transcript_text) > 2000 else transcript_text,
                        height=300,
                        disabled=True
                    )
                
                # Step 2: Generate blog
                with st.spinner("Generating blog from transcript..."):
                    title = video_title if video_title else "YouTube Video"
                    blog_content = generate_blog_with_groq(transcript_text, title)
                    
                    if not blog_content.startswith("Error"):
                        st.success("✅ Blog generated from transcript!")
                        
                        # Store in session state for display in right column
                        st.session_state.blog_content = blog_content
                        st.session_state.transcript_text = transcript_text
                    else:
                        st.error(blog_content)
            else:
                st.error(f"❌ Failed to extract transcript: {error_msg}")
                st.info("This video may not have accessible transcripts.")
    
    with col2:
        st.header("📄 Generated Blog")
        
        if hasattr(st.session_state, 'blog_content'):
            st.markdown("### 📝 Blog Post:")
            st.markdown(st.session_state.blog_content)
            
            # Download button
            st.download_button(
                label="💾 Download Blog",
                data=st.session_state.blog_content,
                file_name="transcript_blog.md",
                mime="text/markdown"
            )
            
            # Show word count
            word_count = len(st.session_state.blog_content.split())
            st.info(f"📊 Blog: {word_count} words | Transcript: {len(st.session_state.transcript_text.split())} words")
            
        else:
            st.info("Blog will appear here after processing")
    
    st.markdown("---")
    st.markdown("**Note:** This app creates blogs using ONLY the actual video transcript content.")

if __name__ == "__main__":
    main()