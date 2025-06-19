"""
Configuration settings for Spotify Playlist Downloader
"""

import os
from pathlib import Path

# Application settings
APP_NAME = "Spotify Playlist Downloader"
APP_VERSION = "2.0.0"
APP_WIDTH = 900
APP_HEIGHT = 700

# API settings
SPOTIFY_SCOPES = "user-library-read playlist-read-private playlist-read-collaborative"
DEFAULT_REDIRECT_URI = "http://localhost:8888/callback"

# Download settings
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "Spotify_Downloads")
AUDIO_FORMAT = "mp3"
AUDIO_QUALITY = "192"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# YouTube-dl settings
YT_DLP_OPTIONS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': AUDIO_FORMAT,
        'preferredquality': AUDIO_QUALITY,
    }],
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'extractaudio': True,
    'audioformat': AUDIO_FORMAT,
}

# Logging settings
LOG_FILE = "downloader.log"
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = "INFO"

# UI settings
PROGRESS_UPDATE_INTERVAL = 1000  # milliseconds
MAX_SEARCH_RESULTS = 3  # Number of YouTube videos to try per track

# File naming
INVALID_CHARS = '<>:"/\\|?*'
MAX_FILENAME_LENGTH = 255

def get_safe_filename(filename: str) -> str:
    """Create a safe filename by removing invalid characters"""
    # Replace invalid characters with underscore
    for char in INVALID_CHARS:
        filename = filename.replace(char, '_')
    
    # Remove multiple underscores and trim
    filename = '_'.join(filename.split())
    
    # Limit length
    if len(filename) > MAX_FILENAME_LENGTH:
        filename = filename[:MAX_FILENAME_LENGTH].rstrip('_')
    
    return filename

def get_yt_dlp_options(output_path: str, filename: str) -> dict:
    """Get yt-dlp options with dynamic output path"""
    options = YT_DLP_OPTIONS.copy()
    options['outtmpl'] = os.path.join(output_path, f"{filename}.%(ext)s")
    return options