from __future__ import unicode_literals
import requests
import re
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from secrets_API import API_KEY
#import youtube_dl #OLD BROKEN
import yt_dlp
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import os
import zipfile
from flask_socketio import SocketIO
import logging
from logging.handlers import TimedRotatingFileHandler


app = Flask(__name__)
socketio = SocketIO(app)


#----------------------GLOBAL SET UP ----------------------------------------------------------------------
# Global variable to store progress value
global_progress = 0

#Global variable to track the amount of ongoign downloads.
ongoing_downloads = 0

# Get the user's home directory
home_directory = os.path.expanduser("~")
# Set the download path as a subdirectory in the user's home directory
download_path = os.path.join(home_directory, 'VidyardDL-TMP')

if not os.path.exists(download_path):
        try:
            os.makedirs(download_path)
        except Exception as e:
            app.logger.error(f"Error creating download folder: {str(e)}")

# Configure logging
log_folder = 'logs'
os.makedirs(log_folder, exist_ok=True)
log_file_path = os.path.join(log_folder, 'DownloadLog.log')
logging.basicConfig(filename=log_file_path,level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add a timed rotating file handler to create daily log files
log_handler = TimedRotatingFileHandler('DownloadLog.log', when='midnight', interval=1, backupCount=30)
log_handler.setLevel(logging.INFO)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.getLogger().addHandler(log_handler)

logging.info('YouTube Downloads Log')



# Load Browser Favorite Icon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
        'favicon.ico',mimetype='image/vnd.microsoft.icon')
#----------------------GLOBAL SET UP ----------------------------------------------------------------------

#------------------------------Functions------------------------------------------------------------------
# Function to clean up files
def clean_up_files(path):
    directory = path
    print(f"Cleaning files in: {path}")
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            app.logger.error(f"Error removing file {file_path}: {str(e)}")

#-----------------------------------Vidyard Functions-------------------------
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
#-----------------------------------Vidyard Functions------------------------- 
#YoutubeDL Progress extraction
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

#YOUTUBEDL call
def download_yt(youtube_url, download_path,client_ip):
    options = {
        #'format': 'bestvideo+bestaudio/best',
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
        'outtmpl': f'{download_path}/%(title)s.%(ext)s',
        'verbose': True,
        'progress_hooks': [progress_hook],
    }
    
    with yt_dlp.YoutubeDL(options) as ydl:
        try:
            info_dict = ydl.extract_info(youtube_url, download=False)
            file_path = ydl.prepare_filename(info_dict)
            ydl.download([youtube_url])

            # Log video information using the logging module
            log_message = f"Client IP: {client_ip}, URL: {youtube_url}, Title: {info_dict['title']}"
            logging.info(log_message)

            return True, file_path, None
        except yt_dlp.DownloadError as e:
            return False, None, str(e)
        
#Zip function for list input     
def send_multiple_files(file_paths):
    # Create a zip file containing all the files
    zip_file_path = os.path.join(download_path, 'downloaded_files.zip')
    with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
        for file_path in file_paths:
            zip_file.write(file_path, os.path.basename(file_path))

    # Return the zip file as an attachment
    return send_file(zip_file_path, as_attachment=True)
#------------------------------Functions------------------------------------------------------------------


#------------------------------MAIN APP--------------------------------------------------------------------
#set up webhook
@socketio.on('download_complete')
def handle_download_complete():
    global ongoing_downloads
    #ongoing_downloads -= 1
    print ("Ongoing downloads: ", ongoing_downloads)

    if ongoing_downloads == 0:
        # Emit acknowledgment only when all downloads are complete
        print("Multi-download complete")
        socketio.emit('download_complete_ack', {'message': 'Multi-download complete'})

#Index logic
@app.route('/', methods=['GET', 'POST'])
def home():
    # Access client IP address
    client_ip = request.remote_addr
    if request.method == 'POST':
        print("Received a POST request")

        # Debug printing for form data
        print(f"Form Data: {request.form}")

        if 'youtubeForm' in request.form:
            youtube_list = request.form.get('youtube_list')

            if youtube_list:
                print("youtube list detected: ",youtube_list)
                #Seperate the input into a proper list.
                youtube_urls = youtube_list.split('\n')
                #store the downlaods
                file_paths = []

                global ongoing_downloads
                ongoing_downloads = len(youtube_urls)

                for url in youtube_urls:
                    success, file_path, error_message = download_yt(url, download_path, client_ip)
                    if success:
                        print(f"YouTube download successful: {file_path}")
                        file_paths.append(file_path)

                        ongoing_downloads -= 1
                        #Call the websocket, will only go through when ongoingdownlaods == 0
                        handle_download_complete()
                    else:
                        print(f"YouTube download failed. Error: {error_message}")

                 # After the loop, send all the files in the response
                if file_paths:
                    print("All files downlaoded, Sending as attachment.")
                    return send_multiple_files(file_paths)
                else:
                    return render_template('error.html', message='All YouTube downloads failed.')
            
            else:
                #The single video was submitted
                print("YouTube Single form submitted")
                youtube_url = request.form['youtube_url']
                print(f"YouTube URL: {youtube_url}")
                print(f"Download Path: {download_path}")
                # Call the function to download YouTube video
                success,file_path, error_message = download_yt(youtube_url, download_path, client_ip) #SENDING the client IP here!
                print(f"THE FILE PATH: {file_path}")
                if success:
                    print("YouTube download successful")
                    print(f"THE FILE PATH IS: {file_path}")
                    
                    
                    ongoing_downloads = 0 #Set to 0 as we are downloading a single video.
                    #Call this just in case to prevent GET spam in some edge cases.
                    handle_download_complete()
                    return send_file(file_path, as_attachment=True)
                
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

#Route to report progress
@app.route('/tydl', methods=['GET'])
def download_progress():
    print(f"GLOBAL progress': {global_progress}")
    return jsonify({'progress': global_progress})

#Route to reset progress
@app.route('/reset_progress', methods=['GET'])
def reset_progress():
    global global_progress
    global_progress = 0
    print(f"GLOBAL progress RESET': {global_progress}")
    return jsonify({'message': 'Progress reset successfully'})

#---------------------------------------------------------------------------------------------

# Schedule the clean_up_files function to run every 10 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=clean_up_files,  # Pass the function itself, not the result
    args=[download_path],  # Pass arguments to the function using the 'args' parameter
    trigger=IntervalTrigger(minutes=10),
    id='clean_up_job',
    name='Clean up files every 10 minutes'
)
scheduler.start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=3000)
    
    
    