import os
import re
import json
import threading
import time
import urllib.parse
import urllib.request
import string
from pathlib import Path
from typing import Dict, List, Optional
import webview
import requests
from dotenv import load_dotenv
import spotipy
from spotipy import SpotifyOAuth
from spotipy.oauth2 import SpotifyOauthError
from yt_dlp import YoutubeDL
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('downloader.log'),
        logging.StreamHandler()
    ]
)

class SpotifyDownloaderAPI:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.redirect_uri = os.getenv("REDIRECT_URL", "http://localhost:8888/callback")
        
        self.sp_oauth = None
        self.sp = None
        self.is_downloading = False
        self.download_progress = {"current": 0, "total": 0, "status": "idle"}
        
        # Default download path
        self.download_path = str(Path.home() / "Downloads" / "Spotify_Downloads")
        
        self._setup_spotify_auth()
        
    def _setup_spotify_auth(self):
        """Setup Spotify authentication"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Spotify credentials not found in .env file")
                
            self.sp_oauth = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope="user-library-read playlist-read-private playlist-read-collaborative",
                cache_path=".spotify_cache"
            )
            
            # Try to get cached token
            token_info = self.sp_oauth.get_cached_token()
            if token_info:
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                
        except Exception as e:
            logging.error(f"Spotify OAuth setup error: {e}")
            
    def get_auth_url(self):
        """Get Spotify authorization URL"""
        if not self.sp_oauth:
            return {"error": "Spotify OAuth not initialized"}
        return {"auth_url": self.sp_oauth.get_authorize_url()}
        
    def authenticate(self, auth_code: str):
        """Authenticate with Spotify using authorization code"""
        try:
            token_info = self.sp_oauth.get_access_token(auth_code)
            self.sp = spotipy.Spotify(auth=token_info['access_token'])
            return {"success": True, "message": "Authentication successful"}
        except Exception as e:
            logging.error(f"Authentication error: {e}")
            return {"error": str(e)}
            
    def is_authenticated(self):
        """Check if user is authenticated"""
        return {"authenticated": self.sp is not None}
        
    def extract_playlist_id(self, playlist_url: str) -> Optional[str]:
        """Extract playlist ID from Spotify URL"""
        patterns = [
            r'playlist/([a-zA-Z0-9]+)',
            r'playlist:([a-zA-Z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, playlist_url)
            if match:
                return match.group(1)
        return None
        
    def get_playlist_info(self, playlist_url: str):
        """Get playlist information"""
        try:
            if not self.sp:
                return {"error": "Not authenticated with Spotify"}
                
            playlist_id = self.extract_playlist_id(playlist_url)
            if not playlist_id:
                return {"error": "Invalid Spotify playlist URL"}
                
            playlist = self.sp.playlist(playlist_id)
            track_count = playlist['tracks']['total']
            
            return {
                "success": True,
                "name": playlist['name'],
                "description": playlist['description'],
                "track_count": track_count,
                "owner": playlist['owner']['display_name'],
                "image": playlist['images'][0]['url'] if playlist['images'] else None
            }
            
        except Exception as e:
            logging.error(f"Error getting playlist info: {e}")
            return {"error": str(e)}
            
    def set_download_path(self, path: str):
        """Set download directory"""
        try:
            self.download_path = path
            os.makedirs(path, exist_ok=True)
            return {"success": True, "path": path}
        except Exception as e:
            return {"error": f"Invalid path: {str(e)}"}
            
    def get_download_path(self):
        """Get current download path"""
        return {"path": self.download_path}
        
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system usage"""
        valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
        return ''.join(c for c in filename if c in valid_chars)
        
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Fetch all tracks from a playlist"""
        tracks = []
        offset = 0
        limit = 100
        
        while True:
            response = self.sp.playlist_tracks(playlist_id, limit=limit, offset=offset)
            tracks.extend(response['items'])
            
            if len(response['items']) < limit:
                break
            offset += limit
            
        return tracks
        
    def download_track(self, track_info: Dict, download_folder: str) -> bool:
        """Download a single track"""
        try:
            track = track_info['track']
            if not track or track['type'] != 'track':
                return False
                
            artist_name = track['artists'][0]['name']
            track_name = track['name']
            
            sanitized_name = self.sanitize_filename(f"{artist_name} - {track_name}")
            final_file = os.path.join(download_folder, f"{sanitized_name}.mp3")
            
            # Skip if already exists
            if os.path.exists(final_file):
                logging.info(f"Skipping existing file: {sanitized_name}")
                return True
                
            # Search YouTube
            search_query = urllib.parse.quote(f"{track_name} {artist_name} official")
            try:
                html = urllib.request.urlopen(f"https://www.youtube.com/results?search_query={search_query}")
                video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
            except Exception as e:
                logging.warning(f"Error searching YouTube for {sanitized_name}: {e}")
                return False
            
            if not video_ids:
                logging.warning(f"No YouTube videos found for: {sanitized_name}")
                return False
                
            # Try downloading from YouTube with improved options
            for video_id in video_ids[:3]:  # Try first 3 results
                try:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    ydl_opts = {
                        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
                        'outtmpl': os.path.join(download_folder, f'{sanitized_name}.%(ext)s'),
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'noplaylist': True,
                        'quiet': True,
                        'no_warnings': True,
                        'ignoreerrors': True,
                        'extract_flat': False,
                        'writethumbnail': False,
                        'writeinfojson': False,
                        'cookiefile': None,  # Remove cookies for now
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['android', 'web'],
                                'skip': ['hls', 'dash'],
                            }
                        },
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                    }
                    
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.download([video_url])
                        logging.info(f"Downloaded: {sanitized_name}")
                        return True
                        
                except Exception as e:
                    logging.warning(f"Error downloading video {video_id}: {e}")
                    continue
                    
            return False
            
        except Exception as e:
            logging.error(f"Error downloading track: {e}")
            return False
            
    def start_download(self, playlist_url: str):
        """Start downloading playlist in background thread"""
        def download_worker():
            try:
                self.is_downloading = True
                self.download_progress = {"current": 0, "total": 0, "status": "starting"}
                
                # Get playlist info
                playlist_id = self.extract_playlist_id(playlist_url)
                if not playlist_id:
                    self.download_progress["status"] = "error"
                    self.download_progress["error"] = "Invalid playlist URL"
                    return
                    
                playlist = self.sp.playlist(playlist_id)
                playlist_name = self.sanitize_filename(playlist['name'])
                
                # Create download folder
                download_folder = os.path.join(self.download_path, playlist_name)
                os.makedirs(download_folder, exist_ok=True)
                
                # Get all tracks
                tracks = self.get_playlist_tracks(playlist_id)
                total_tracks = len(tracks)
                
                self.download_progress["total"] = total_tracks
                self.download_progress["status"] = "downloading"
                
                successful_downloads = 0
                
                for i, track_info in enumerate(tracks):
                    if not self.is_downloading:
                        self.download_progress["status"] = "cancelled"
                        return
                        
                    self.download_progress["current"] = i + 1
                    self.download_progress["current_track"] = f"{track_info['track']['artists'][0]['name']} - {track_info['track']['name']}"
                    
                    if self.download_track(track_info, download_folder):
                        successful_downloads += 1
                        
                self.download_progress["status"] = "completed"
                self.download_progress["successful"] = successful_downloads
                self.is_downloading = False
                
            except Exception as e:
                logging.error(f"Download error: {e}")
                self.download_progress["status"] = "error"
                self.download_progress["error"] = str(e)
                self.is_downloading = False
                
        if not self.is_downloading:
            threading.Thread(target=download_worker, daemon=True).start()
            return {"success": True, "message": "Download started"}
        else:
            return {"error": "Download already in progress"}
            
    def stop_download(self):
        """Stop current download"""
        self.is_downloading = False
        return {"success": True, "message": "Download stopped"}
        
    def get_download_progress(self):
        """Get current download progress"""
        return self.download_progress
        
    def open_download_folder(self):
        """Open download folder in file explorer"""
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                os.startfile(self.download_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", self.download_path])
            else:  # Linux
                subprocess.run(["xdg-open", self.download_path])
                
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}
    
    def browse_folder(self):
        """Open a native folder picker and return the chosen path."""
        try:
            # Get the current window
            if webview.windows:
                window = webview.windows[0]
                # Use the correct method to create file dialog
                paths = window.create_file_dialog(webview.FOLDER_DIALOG)
                if paths and len(paths) > 0:
                    folder = paths[0]
                    # Update the download_path in the API
                    self.download_path = folder
                    os.makedirs(folder, exist_ok=True)
                    return {"path": folder}
                else:
                    return {"error": "No folder selected"}
            else:
                return {"error": "No window available"}
        except Exception as e:
            logging.error(f"Error in browse_folder: {e}")
            return {"error": f"Error selecting folder: {str(e)}"}

def create_html():
    """Create the HTML interface"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Spotify Playlist Downloader</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {
                theme: {
                    extend: {
                        colors: {
                            spotify: {
                                green: '#1db954',
                                black: '#191414',
                                gray: '#535353'
                            }
                        }
                    }
                }
            }
        </script>
    </head>
    <body class="bg-gradient-to-br from-spotify-black to-gray-900 text-white min-h-screen">
        <div class="container mx-auto px-4 py-8 max-w-4xl">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold mb-2 bg-gradient-to-r from-spotify-green to-green-400 bg-clip-text text-transparent">
                    Spotify Playlist Downloader
                </h1>
                <p class="text-gray-400">Download your favorite Spotify playlists for offline listening</p>
            </div>

            <!-- Auth Section -->
            <div id="auth-section">
                <div class="bg-gray-800 rounded-lg p-6 mb-6">
                    <h2 class="text-xl font-semibold mb-4">Spotify Authentication Required</h2>
                    <p class="text-gray-300 mb-4">Please authenticate with Spotify to access your playlists.</p>
                    <button id="auth-btn" class="bg-spotify-green hover:bg-green-600 text-white px-6 py-2 rounded-lg transition-colors">
                        Connect to Spotify
                    </button>
                </div>
            </div>

            <!-- Main Interface -->
            <div id="main-interface" class="hidden space-y-6">
                <!-- Playlist Input -->
                <div class="bg-gray-800 rounded-lg p-6">
                    <h2 class="text-xl font-semibold mb-4">Enter Playlist URL</h2>
                    <div class="flex flex-col sm:flex-row gap-3">
                        <input 
                            type="text" 
                            id="playlist-url" 
                            placeholder="https://open.spotify.com/playlist/..." 
                            class="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-spotify-green"
                        >
                        <button 
                            id="analyze-btn" 
                            class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors whitespace-nowrap"
                        >
                            Analyze Playlist
                        </button>
                    </div>
                </div>

                <!-- Playlist Info -->
                <div id="playlist-info" class="hidden bg-gray-800 rounded-lg p-6">
                    <div class="flex flex-col sm:flex-row gap-4">
                        <img id="playlist-image" src="" alt="Playlist Cover" class="w-24 h-24 rounded-lg mx-auto sm:mx-0">
                        <div class="flex-1 text-center sm:text-left">
                            <h3 id="playlist-name" class="text-xl font-semibold mb-2"></h3>
                            <p id="playlist-description" class="text-gray-400 mb-2"></p>
                            <div class="flex flex-col sm:flex-row sm:gap-6 gap-2 text-sm text-gray-300">
                                <span>By <span id="playlist-owner"></span></span>
                                <span><span id="playlist-tracks"></span> tracks</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Download Settings -->
                <div id="download-settings" class="hidden bg-gray-800 rounded-lg p-6">
                    <h2 class="text-xl font-semibold mb-4">Download Settings</h2>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium mb-2">Download Location</label>
                            <div class="flex gap-3">
                                <input 
                                    type="text" 
                                    id="download-path" 
                                    readonly 
                                    class="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white"
                                >
                                <button 
                                    id="browse-btn" 
                                    class="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors"
                                >
                                    Browse
                                </button>
                            </div>
                        </div>
                        <div class="bg-yellow-900/20 border border-yellow-600/30 rounded-lg p-4">
                            <p class="text-yellow-400 text-sm">
                                <strong>Note:</strong> This tool searches YouTube for audio tracks matching your Spotify playlist. 
                                Due to YouTube's restrictions, some downloads may fail. Make sure you have FFmpeg installed.
                            </p>
                        </div>
                        <button 
                            id="download-btn" 
                            class="w-full bg-spotify-green hover:bg-green-600 text-white py-3 rounded-lg font-semibold transition-colors"
                        >
                            Start Download
                        </button>
                    </div>
                </div>

                <!-- Progress Section -->
                <div id="progress-section" class="hidden bg-gray-800 rounded-lg p-6">
                    <h2 class="text-xl font-semibold mb-4">Download Progress</h2>
                    <div class="space-y-4">
                        <div>
                            <div class="flex justify-between text-sm mb-2">
                                <span id="progress-text">Preparing download...</span>
                                <span id="progress-count">0/0</span>
                            </div>
                            <div class="w-full bg-gray-700 rounded-full h-2">
                                <div id="progress-bar" class="bg-spotify-green h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                            </div>
                        </div>
                        <div id="current-track" class="text-sm text-gray-400"></div>
                        <div class="flex gap-3">
                            <button 
                                id="stop-btn" 
                                class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg transition-colors"
                            >
                                Stop Download
                            </button>
                            <button 
                                id="open-folder-btn" 
                                class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
                            >
                                Open Download Folder
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Error/Success Messages -->
                <div id="message-area"></div>
            </div>
        </div>

        <script>
            class SpotifyDownloader {
                constructor() {
                    this.checkAuthStatus();
                    this.bindEvents();
                    this.loadDownloadPath();
                    this.startProgressPolling();
                }

                async checkAuthStatus() {
                    try {
                        const result = await pywebview.api.is_authenticated();
                        if (result.authenticated) {
                            document.getElementById('auth-section').classList.add('hidden');
                            document.getElementById('main-interface').classList.remove('hidden');
                        } else {
                            document.getElementById('auth-section').classList.remove('hidden');
                            document.getElementById('main-interface').classList.add('hidden');
                        }
                    } catch (error) {
                        this.showMessage('Error checking authentication status', 'error');
                    }
                }

                async loadDownloadPath() {
                    try {
                        const result = await pywebview.api.get_download_path();
                        document.getElementById('download-path').value = result.path;
                    } catch (error) {
                        console.error('Error loading download path:', error);
                    }
                }

                bindEvents() {
                    document.getElementById('auth-btn').addEventListener('click', () => this.handleAuth());
                    document.getElementById('analyze-btn').addEventListener('click', () => this.analyzePlaylist());
                    document.getElementById('download-btn').addEventListener('click', () => this.startDownload());
                    document.getElementById('stop-btn').addEventListener('click', () => this.stopDownload());
                    document.getElementById('open-folder-btn').addEventListener('click', () => this.openFolder());
                    document.getElementById('browse-btn').addEventListener('click', async () => {
                        try {
                            const result = await pywebview.api.browse_folder();
                            if (result.path) {
                                document.getElementById('download-path').value = result.path;
                                this.showMessage('Download path updated successfully', 'success');
                            } else if (result.error) {
                                this.showMessage(result.error, 'error');
                            }
                        } catch (e) {
                            this.showMessage('Error selecting folder', 'error');
                        }
                    });
                    
                    // Enter key support
                    document.getElementById('playlist-url').addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') this.analyzePlaylist();
                    });
                }

                async handleAuth() {
                    try {
                        const result = await pywebview.api.get_auth_url();
                        if (result.auth_url) {
                            window.open(result.auth_url, '_blank');
                            const authCode = prompt('Please enter the authorization code from the redirect URL:');
                            if (authCode) {
                                const authResult = await pywebview.api.authenticate(authCode);
                                if (authResult.success) {
                                    this.showMessage('Authentication successful!', 'success');
                                    this.checkAuthStatus();
                                } else {
                                    this.showMessage(authResult.error, 'error');
                                }
                            }
                        }
                    } catch (error) {
                        this.showMessage('Authentication failed', 'error');
                    }
                }

                async analyzePlaylist() {
                    const url = document.getElementById('playlist-url').value.trim();
                    if (!url) {
                        this.showMessage('Please enter a Spotify playlist URL', 'error');
                        return;
                    }

                    document.getElementById('analyze-btn').disabled = true;
                    document.getElementById('analyze-btn').textContent = 'Analyzing...';

                    try {
                        const result = await pywebview.api.get_playlist_info(url);
                        if (result.success) {
                            this.displayPlaylistInfo(result);
                            document.getElementById('download-settings').classList.remove('hidden');
                        } else {
                            this.showMessage(result.error, 'error');
                        }
                    } catch (error) {
                        this.showMessage('Error analyzing playlist', 'error');
                    } finally {
                        document.getElementById('analyze-btn').disabled = false;
                        document.getElementById('analyze-btn').textContent = 'Analyze Playlist';
                    }
                }

                displayPlaylistInfo(info) {
                    document.getElementById('playlist-name').textContent = info.name;
                    document.getElementById('playlist-description').textContent = info.description || 'No description';
                    document.getElementById('playlist-owner').textContent = info.owner;
                    document.getElementById('playlist-tracks').textContent = info.track_count;
                    
                    if (info.image) {
                        document.getElementById('playlist-image').src = info.image;
                    }
                    
                    document.getElementById('playlist-info').classList.remove('hidden');
                }

                async startDownload() {
                    const url = document.getElementById('playlist-url').value.trim();
                    if (!url) return;

                    try {
                        const result = await pywebview.api.start_download(url);
                        if (result.success) {
                            document.getElementById('progress-section').classList.remove('hidden');
                            document.getElementById('download-btn').disabled = true;
                        } else {
                            this.showMessage(result.error, 'error');
                        }
                    } catch (error) {
                        this.showMessage('Error starting download', 'error');
                    }
                }

                async stopDownload() {
                    try {
                        await pywebview.api.stop_download();
                        document.getElementById('download-btn').disabled = false;
                    } catch (error) {
                        this.showMessage('Error stopping download', 'error');
                    }
                }

                async openFolder() {
                    try {
                        await pywebview.api.open_download_folder();
                    } catch (error) {
                        this.showMessage('Error opening folder', 'error');
                    }
                }

                startProgressPolling() {
                    setInterval(async () => {
                        try {
                            const progress = await pywebview.api.get_download_progress();
                            this.updateProgress(progress);
                        } catch (error) {
                            // Silently handle errors in polling
                        }
                    }, 1000);
                }

                updateProgress(progress) {
                    const progressSection = document.getElementById('progress-section');
                    if (progress.status === 'idle') {
                        progressSection.classList.add('hidden');
                        return;
                    }

                    progressSection.classList.remove('hidden');
                    
                    const percentage = progress.total > 0 ? (progress.current / progress.total) * 100 : 0;
                    document.getElementById('progress-bar').style.width = percentage + '%';
                    document.getElementById('progress-count').textContent = `${progress.current}/${progress.total}`;
                    
                    let statusText = progress.status;
                    switch (progress.status) {
                        case 'starting':
                            statusText = 'Preparing download...';
                            break;
                        case 'downloading':
                            statusText = 'Downloading tracks...';
                            break;
                        case 'completed':
                            statusText = `Completed! ${progress.successful || progress.current} tracks downloaded.`;
                            document.getElementById('download-btn').disabled = false;
                            break;
                        case 'cancelled':
                            statusText = 'Download cancelled';
                            document.getElementById('download-btn').disabled = false;
                            break;
                        case 'error':
                            statusText = 'Download error: ' + (progress.error || 'Unknown error');
                            document.getElementById('download-btn').disabled = false;
                            break;
                    }
                    
                    document.getElementById('progress-text').textContent = statusText;
                    
                    if (progress.current_track) {
                        document.getElementById('current-track').textContent = `Downloading: ${progress.current_track}`;
                    }
                }

                showMessage(message, type = 'info') {
                    const messageArea = document.getElementById('message-area');
                    const colorClass = type === 'error' ? 'bg-red-600' : type === 'success' ? 'bg-green-600' : 'bg-blue-600';
                    
                    messageArea.innerHTML = `
                        <div class="${colorClass} text-white p-4 rounded-lg mb-4">
                            ${message}
                        </div>
                    `;
                    
                    setTimeout(() => {
                        messageArea.innerHTML = '';
                    }, 5000);
                }
            }

            // Initialize when page loads
            window.addEventListener('DOMContentLoaded', () => {
                new SpotifyDownloader();
            });
        </script>
    </body>
    </html>
    """

def main():
    # Create API instance
    api = SpotifyDownloaderAPI()
    
    # Create and start webview
    window = webview.create_window(
        'Spotify Playlist Downloader',
        html=create_html(),
        width=900,
        height=700,
        resizable=True,
        js_api=api
    )
    
    webview.start(debug=False)

if __name__ == '__main__':
    main()