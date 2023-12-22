import requests
import re
from flask import Flask, render_template, request
from secrets_API import API_KEY



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
#------------------------------Functions------------------------------------------------------------------


#------------------------------MAIN APP--------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
def home():

    if request.method == 'POST':
        vidyard_url = request.form['vidyard_url']
        uuid_input = request.form['uuid_input']

        # Check if either the URL or UUID is provided
        if vidyard_url or uuid_input:
            # Use the UUID if provided; otherwise, extract it from the URL
            uuid = uuid_input if uuid_input else extract_uuid(vidyard_url)

            if uuid:
                download_links = get_download_links(uuid)
                return render_template('result.html', download_links=download_links)
            else:
                return render_template('error.html', message="Error: Unable to extract UUID from the provided input.")
        else:
            return render_template('error.html', message="Error: Please provide either the Vidyard URL or UUID.")

    return render_template('index.html')

#---------------------------------------------------------------------------------------------


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)




















'''
# Prompt the user to input a Vidyard URL
vidyard_url = input("Enter the Vidyard URL: ")

# Extract the UUID from the URL
uuid_input = extract_uuid(vidyard_url)


if uuid_input:
    # Replace the {uuid} placeholder in the endpoint with the extracted UUID
    url = download_links_endpoint.format(uuid=uuid_input)

    # Make the API request
    response = requests.get(url, params=params, headers=headers)

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        try:
            # Attempt to parse the response as JSON
            data = response.json()

            # Check if the response is a list and not empty
            if isinstance(data, list) and data:
                # Extract the first item in the list
                video_info = data[0]

                # Check if the item has 'download_links' key
                if 'download_links' in video_info:
                    print("Download Links:")
                    download_links = video_info['download_links']

                    # Print links for different qualities
                    for quality, link in download_links.items():
                        print(f"{quality}: {link}")
                else:
                    print("No 'download_links' key found in the response.")
            else:
                print("Invalid response format or empty response.")
        except ValueError:
            print("Error: Response does not contain valid JSON.")
    else:
        # Print an error message if the request was unsuccessful
        print(f"Error: {response.status_code} - {response.text}")
else:
    print("Error: Unable to extract UUID from the provided URL.")

    '''