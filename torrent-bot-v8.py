import os
import subprocess
import time
import requests
import json
import re
from pathlib import Path
import shutil
from urllib.parse import urlparse, parse_qs

def install_dependencies():
    """Install required packages"""
    print("🔧 Installing dependencies...")
    subprocess.run(["apt-get", "update", "-qq"], check=True)
    subprocess.run(["apt-get", "install", "-y", "-qq", "aria2"], check=True)
    print("✅ Dependencies installed!")

def sanitize_filename(filename):
    """Sanitize filename for safe file operations"""
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)  # Replace spaces with underscores
    return filename[:100]  # Limit length

def get_torrent_info(magnet_link):
    """Extract torrent name from magnet link"""
    try:
        # Parse the magnet link to extract the display name
        if 'dn=' in magnet_link:
            name_match = re.search(r'dn=([^&]+)', magnet_link)
            if name_match:
                import urllib.parse
                name = urllib.parse.unquote_plus(name_match.group(1))
                return sanitize_filename(name)
    except:
        pass
    return f"torrent_{int(time.time())}"

def download_torrent(magnet_link, download_dir="/content/downloads"):
    """Download torrent using aria2c"""
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"🔄 Starting download...")
    print(f"📁 Download directory: {download_dir}")
    
    # Aria2c command with progress updates
    cmd = [
        "aria2c",
        "--seed-time=0",  # Don't seed after download
        "--max-upload-limit=1K",  # Minimal upload to save bandwidth
        "--dir=" + download_dir,
        "--summary-interval=1",  # Show progress every second
        "--download-result=hide",
        "--console-log-level=warn",  # Reduce console output
        magnet_link
    ]
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 universal_newlines=True, bufsize=1)
        
        last_progress_line = ""
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                clean_output = output.strip()
                
                # Filter out unwanted lines and only show meaningful progress
                if clean_output and not any(x in clean_output.lower() for x in [
                    '---', 'download result', 'gid:', 'status:active', 
                    'uri:', 'local:', 'remote:', '[metadata]'
                ]):
                    # Look for actual progress indicators
                    if any(indicator in clean_output for indicator in [
                        'DL:', 'CN:', '%', 'ETA:', 'SIZE:', 'SEED'
                    ]):
                        # Clear the line and show new progress
                        if clean_output != last_progress_line:
                            print(f"\r{' ' * 120}\r", end="")  # Clear line
                            print(f"📥 {clean_output[:100]}", end="", flush=True)
                            last_progress_line = clean_output
        
        return_code = process.poll()
        print()  # New line after progress updates
        if return_code == 0:
            print("✅ Download completed successfully!")
            return True
        else:
            print(f"❌ Download failed with return code: {return_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error during download: {str(e)}")
        return False

def create_zip(source_dir, zip_name):
    """Create zip file with move option to save space"""
    print(f"📦 Creating zip archive: {zip_name}")
    
    try:
        zip_path = f"/content/{zip_name}.zip"
        
        # Use zip command with -m (move) option to move files into zip
        # This frees up space immediately as files are moved, not copied
        cmd = ["zip", "-r", "-m", zip_path, "."]
        
        # Change to source directory and run zip command
        result = subprocess.run(cmd, cwd=source_dir, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Zip created with files moved (space saved): {zip_path}")
            # Remove empty source directory
            try:
                os.rmdir(source_dir)
                print(f"🗑️ Removed empty download directory")
            except:
                pass
            return zip_path
        else:
            print(f"❌ Error creating zip: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating zip: {str(e)}")
        return None

def upload_to_gofile(file_path):
    """Upload file to gofile.io"""
    print(f"☁️ Uploading to GoFile...")
    
    try:
        upload_url = "https://upload.gofile.io/uploadfile"
        
        # Upload file with progress
        with open(file_path, 'rb') as f:
            files = {'file': f}
            
            print(f"📤 Uploading file...")
            response = requests.post(upload_url, files=files)
            
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "ok":
                download_page = result["data"]["downloadPage"]
                print(f"✅ Upload successful!")
                return download_page
            else:
                print(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
                return None
        else:
            print(f"❌ Upload failed with status code: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error uploading file: {str(e)}")
        return None

def cleanup_files(*file_paths):
    """Clean up downloaded files"""
    print("🧹 Cleaning up files...")
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"🗑️ Deleted file: {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    print(f"🗑️ Deleted directory: {file_path}")
        except Exception as e:
            print(f"⚠️ Could not delete {file_path}: {str(e)}")
    
    # Also clean up any remaining empty directories in downloads
    try:
        downloads_dir = "/content/downloads"
        if os.path.exists(downloads_dir) and not os.listdir(downloads_dir):
            os.rmdir(downloads_dir)
            print(f"🗑️ Removed empty downloads directory")
    except:
        pass

def main():
    """Main function"""
    print("🚀 Torrent Download & Upload Bot")
    print("=" * 50)
    
    # Install dependencies
    install_dependencies()
    
    # Get magnet link from user
    magnet_link = input("📎 Enter magnet link: ").strip()
    
    if not magnet_link.startswith("magnet:"):
        print("❌ Invalid magnet link!")
        return
    
    # Extract torrent name for smart naming
    torrent_name = get_torrent_info(magnet_link)
    print(f"📝 Detected name: {torrent_name}")
    
    download_dir = "/content/downloads"
    
    try:
        # Download torrent
        if not download_torrent(magnet_link, download_dir):
            return
        
        # Check if download directory has content
        if not os.path.exists(download_dir) or not os.listdir(download_dir):
            print("❌ No files were downloaded!")
            return
        
        # Create zip file
        zip_path = create_zip(download_dir, torrent_name)
        if not zip_path:
            return
        
        # Upload to GoFile
        download_page = upload_to_gofile(zip_path)
        
        if download_page:
            print("\n" + "=" * 50)
            print("🎉 PROCESS COMPLETED SUCCESSFULLY!")
            print(f"📁 File: {torrent_name}.zip")
            print(f"🔗 Download URL: {download_page}")
            print("=" * 50)
        
        # Cleanup
        cleanup_files(zip_path, download_dir)
        
    except KeyboardInterrupt:
        print("\n❌ Process interrupted by user")
        cleanup_files(download_dir)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        cleanup_files(download_dir)

# Run the script
if __name__ == "__main__":
    main()
