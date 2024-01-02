from __future__ import unicode_literals
import requests
import re
from flask import Flask, render_template, request, jsonify
from secrets_API import API_KEY
#import youtube_dl #OLD BROKEN
import yt_dlp



import os
# Global variable to store progress value
global_progress = 0


app = Flask(__name__)

#------------------------------Functions------------------------------------------------------------------
def extract_uuid(url):
    match = re.search(r'/watch/([^/?]+)', url)
    if match:
        return match.group(1)
    return None

def get_download_links(uuid):
    download_links_endpoint = "https://api.vidyard.com/dashboard/v1/players/uuid={uuid}/download_links"
    api_key = API_KEY #Pulled from the secrets.
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    params = {
    'auth_token': api_key
    }
    url = download_links_endpoint.format(uuid=uuid)
    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        try:
            data = response.json()
            if isinstance(data, list) and data:
                video_info = data[0]
                if 'download_links' in video_info:
                    return video_info['download_links']
                else:
                    return None
            else:
                return None
        except ValueError:
            return None
    else:
        return None
    
def progress_hook(d):
    global global_progress

    if d['status'] == 'finished':
        print('Download completed.')
        global_progress = 100  # Set progress to 100 when finished

    elif d['status'] == 'downloading':
        # Extract numeric progress value from '_percent_str' using regex
        match = re.search(r'(\d+\.\d)%', d['_percent_str'])
        if match:
            progress_str = match.group(1)  # Extract the numeric part
            try:
                progress = float(progress_str)
                print(f'Downloading: {progress}% ETA: {d["_eta_str"]}')
                global_progress = progress
            except ValueError:
                print('Failed to convert progress value to float.')
        else:
            print('Failed to extract numeric progress value.')

def download_yt(youtube_url, download_path):
    options = {
        #'format': 'bestvideo+bestaudio/best',
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'outtmpl': f'{download_path}/%(title)s.%(ext)s',
        'verbose': True,
        'progress_hooks': [progress_hook],
    }
    
    with yt_dlp.YoutubeDL(options) as ydl:
        try:
            ydl.download([youtube_url])
            return True, None
        except yt_dlp.DownloadError as e:
            return False, str(e)
#------------------------------Functions------------------------------------------------------------------


#------------------------------MAIN APP--------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        print("Received a POST request")

        # Debug printing for form data
        print(f"Form Data: {request.form}")

        if 'youtubeForm' in request.form:
            # Handle YouTube form submission
            print("YouTube form submitted")
            youtube_url = request.form['youtube_url']
            print(f"YouTube URL: {youtube_url}")
            
            # Get the user's home directory
            home_directory = os.path.expanduser("~")
            # Set the download path as a subdirectory in the user's home directory
            download_path = os.path.join(home_directory, 'Downloads')
            print(f"Download Path: {download_path}")

            # Call the function to download YouTube video
            success, error_message = download_yt(youtube_url, download_path)

            if success:
                print("YouTube download successful")
                return render_template('success.html', download_path=download_path)
            else:
                print(f"YouTube download failed. Error: {error_message}")
                return render_template('error.html', message=f'Error: {error_message}')

        elif 'vidyardForm' in request.form:
            # Handle Vidyard form submission
            print("Vidyard form submitted")
            vidyard_url = request.form['vidyard_url']
            uuid_input = request.form['uuid_input']
            print(f"Vidyard URL: {vidyard_url}, UUID Input: {uuid_input}")

            # Check if either the URL or UUID is provided
            if vidyard_url or uuid_input:
                # Use the UUID if provided; otherwise, extract it from the URL
                uuid = uuid_input if uuid_input else extract_uuid(vidyard_url)
                print(f"Extracted UUID: {uuid}")

                if uuid:
                    download_links = get_download_links(uuid)
                    print(f"Download Links: {download_links}")
                    return render_template('result.html', download_links=download_links)
                else:
                    print("Error: Unable to extract UUID from the provided input.")
                    return render_template('error.html', message="Error: Unable to extract UUID from the provided input.")
            else:
                print("Error: Please provide either the Vidyard URL or UUID.")
                return render_template('error.html', message="Error: Please provide either the Vidyard URL or UUID.")
        else:
            print("Nothing Sumbitted")
            return render_template('error.html', message="Error: Please provide some sort of input")
    
    print("Rendering the index.html page")
    return render_template('index.html')

@app.route('/tydl', methods=['GET'])
def download_progress():
    print(f"GLOBAL progress': {global_progress}")
    return jsonify({'progress': global_progress})

@app.route('/reset_progress', methods=['GET'])
def reset_progress():
    global global_progress
    global_progress = 0
    print(f"GLOBAL progress RESET': {global_progress}")
    return jsonify({'message': 'Progress reset successfully'})

#---------------------------------------------------------------------------------------------


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)