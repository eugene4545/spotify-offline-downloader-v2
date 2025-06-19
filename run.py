#!/usr/bin/env python3
"""
Simple launcher for Spotify Playlist Downloader
Checks prerequisites and launches the app
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all required packages are installed"""
    required_packages = ['webview', 'spotipy', 'yt_dlp', 'requests', 'dotenv']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print("❌ Missing required packages:", ', '.join(missing))
        print("🔧 Run setup: python setup.py")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists and has credentials"""
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        print("🔧 Run setup: python setup.py")
        return False
    
    content = env_file.read_text()
    if "your_spotify_client_id_here" in content:
        print("❌ Please update .env file with your Spotify API credentials")
        print("📖 Visit: https://developer.spotify.com/dashboard")
        return False
    
    return True

def check_ffmpeg():
    """Check if FFmpeg is available"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ FFmpeg not found. Audio downloads may fail.")
        print("📖 Install FFmpeg: https://ffmpeg.org/download.html")
        return False

def main():
    """Launch the app with prerequisite checks"""
    print("🎵 Spotify Playlist Downloader")
    print("=" * 30)
    
    # Check prerequisites
    checks_passed = 0
    total_checks = 3
    
    print("🔍 Checking prerequisites...")
    
    if check_requirements():
        print("✅ Python packages installed")
        checks_passed += 1
    
    if check_env_file():
        print("✅ Spotify credentials configured")
        checks_passed += 1
    
    if check_ffmpeg():
        print("✅ FFmpeg available")
        checks_passed += 1
    
    print(f"\n📊 Prerequisites: {checks_passed}/{total_checks} passed")
    
    if checks_passed == total_checks:
        print("🚀 Starting application...")
        try:
            from app import main as app_main
            app_main()
        except Exception as e:
            print(f"❌ Error starting app: {e}")
            print("🔧 Try running: python app.py directly")
    else:
        print("⚠️  Some prerequisites failed. The app may not work correctly.")
        if input("Continue anyway? (y/n): ").lower() == 'y':
            try:
                from app import main as app_main
                app_main()
            except Exception as e:
                print(f"❌ Error starting app: {e}")

if __name__ == "__main__":
    main()