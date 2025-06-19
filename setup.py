#!/usr/bin/env python3
"""
Setup script for Spotify Playlist Downloader
"""

import os
import sys
import subprocess
from pathlib import Path

def install_requirements():
    """Install required packages"""
    print("Installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        return False

def check_ffmpeg():
    """Check if FFmpeg is installed"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("✅ FFmpeg is installed and accessible")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found. Please install FFmpeg:")
        print("  - Windows: Download from https://ffmpeg.org/download.html and add to PATH")
        print("  - macOS: brew install ffmpeg")
        print("  - Linux: sudo apt install ffmpeg (Ubuntu/Debian)")
        return False

def create_env_template():
    """Create .env template file if it doesn't exist"""
    env_file = Path(".env")
    if not env_file.exists():
        template = """# Spotify API Credentials
# Get these from: https://developer.spotify.com/dashboard
CLIENT_ID=your_spotify_client_id_here
CLIENT_SECRET=your_spotify_client_secret_here
REDIRECT_URL=http://localhost:8888/callback
"""
        env_file.write_text(template)
        print("✅ Created .env template file")
        print("📝 Please edit .env file with your Spotify API credentials")
        return False
    else:
        # Check if .env has actual values
        content = env_file.read_text()
        if "your_spotify_client_id_here" in content:
            print("📝 Please update .env file with your actual Spotify API credentials")
            return False
        print("✅ .env file exists with credentials")
        return True

def build_executable():
    """Build standalone executable using PyInstaller"""
    print("Building standalone executable...")
    try:
        cmd = [
            "pyinstaller",
            "--onefile",
            "--windowed",
            "--name", "SpotifyDownloader",
            "--add-data", ".env:.",
            "--hidden-import", "spotipy",
            "--hidden-import", "yt_dlp",
            "--hidden-import", "webview",
            "app.py"
        ]
        subprocess.check_call(cmd)
        print("✅ Executable built successfully in dist/ folder")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error building executable: {e}")
        return False
    except FileNotFoundError:
        print("❌ PyInstaller not found. Install with: pip install pyinstaller")
        return False

def main():
    """Main setup function"""
    print("🎵 Spotify Playlist Downloader Setup")
    print("=" * 40)
    
    success = True
    
    # Step 1: Install requirements
    if not install_requirements():
        success = False
    
    # Step 2: Check FFmpeg
    if not check_ffmpeg():
        success = False
    
    # Step 3: Create/check .env file
    if not create_env_template():
        success = False
    
    if success:
        print("\n✅ Setup completed successfully!")
        print("🚀 You can now run the app with: python app.py")
        
        # Ask if user wants to build executable
        if input("\nWould you like to build a standalone executable? (y/n): ").lower() == 'y':
            build_executable()
    else:
        print("\n❌ Setup incomplete. Please resolve the issues above.")
        print("📖 Check README.md for detailed setup instructions.")

if __name__ == "__main__":
    main()