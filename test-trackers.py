
"""
This script tests and filters a list of trackers to find out which ones return a valid
response then and saves the valid ones to a file.

Author: Simon Whitehead
Date: 16 April 2024
"""

import requests
import socket
import logging
import struct
from urllib.parse import urlparse

#
#   CONFIGURATION
#

# URL of the raw GitHub content
TRACKER_LIST = "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all.txt"

# Output file to save as. Will be overwritten.
OUTPUT_FILE = "valid_trackers.txt"

# Log file
LOG_FILE = "response_log.txt"

# Array of trackers to skip testing which cause hangs or other issues
SKIP_TRACKERS = ["udp://tracker.theoks.net:6969/announce"]


#
#   FUNCTIONS
#

def is_valid_http_url(url):
    """
    Checks if an HTTP URL returns a valid response.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if the URL returns a valid response, False otherwise.
        int: The status code of the response.
    """
    try:
        response = requests.get(url, timeout=5)
        status_code = response.status_code
        logging.info(f"URL: {url}, Status Code: {status_code}")
        return status_code == 200, status_code
    except requests.exceptions.RequestException as e:
        logging.error(f"URL: {url}, Error: {e}")
        return False, None


def is_valid_udp_endpoint(tracker_url, timeout=10):
    """
    Checks if a UDP endpoint is valid.

    Args:
        tracker_url (str): The UDP endpoint URL to check.
        timeout (int): The timeout value for the UDP socket (default: 10).

    Returns:
        bool: True if the UDP endpoint is valid, False otherwise.
    """
    try:
        # Parse the tracker URL to extract the hostname and port
        parsed_url = urlparse(tracker_url)
        tracker_host = parsed_url.hostname
        tracker_port = parsed_url.port

        # Check if the port is not specified and set it to the default (80)
        if tracker_port is None:
            tracker_port = 80
    except ValueError as e:
        # Handle the case where the URL is not valid
        print(f"Error parsing URL: {e}")
        # You may want to set default values or take other actions as needed
        tracker_host = None
        tracker_port = 80

    # Create a UDP socket with a timeout
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.settimeout(timeout)  # Set the timeout

    try:
        # Build the UDP tracker request
        connection_id = 0x41727101980  # Initial connection ID
        action = 0  # 0 for connect
        transaction_id = 123456  # A random transaction ID

        # Construct the connection request packet
        connection_request = struct.pack(
            '!QII', connection_id, action, transaction_id)

        # Send the connection request
        udp_socket.sendto(connection_request, (tracker_host, tracker_port))

        # Log the UDP request
        logging.info(f"UDP Request sent to {tracker_host}:{tracker_port}")

        # Receive and unpack the connection response
        response, _ = udp_socket.recvfrom(16)
        connection_id, action, transaction_id = struct.unpack('!QII', response)

        # Validate the connection response
        if not response:
            logging.error(
                f"UDP Response from {tracker_host}:{tracker_port} is invalid")
            return False

        # Log the UDP announce response
        logging.info(f"UDP Connection made to {tracker_host}:{tracker_port}")

        return True  # The response is considered valid if we reached this point

    except socket.error as e:
        logging.error(f"UDP Error: {e} for {tracker_host}:{tracker_port}")
        return False
    except socket.timeout:
        logging.error(f"UDP Timeout for {tracker_host}:{tracker_port}")
        return False
    finally:
        udp_socket.close()


def process_trackers_list(url):
    """
    Fetches a list of trackers from a URL, tests their validity, and returns the valid ones.

    Args:
        url (str): The URL of the trackers list.

    Returns:
        list: A list of valid trackers (HTTP URLs and UDP endpoints).
    """
    try:
        response = requests.get(url)
        if response.status_code == 200:
            raw_content = response.text
            tracker_list = raw_content.split('\n')
            # Log the number of trackers fetched
            logging.info(f"Trackers fetched: {len(tracker_list)}")
            valid_trackers = []
            for t in tracker_list:
                if t not in SKIP_TRACKERS:
                    t = t.strip()
                    if t:
                        print(f"Testing {t}")

                        if t.startswith("udp://"):
                            if is_valid_udp_endpoint(t):
                                valid_trackers.append(f"{t}")
                        else:
                            is_valid, status_code = is_valid_http_url(
                                t)
                            if is_valid:
                                valid_trackers.append(f"{t}")
                else:
                    print(f"Skipping {t}")

            return valid_trackers
        else:
            print(
                f"Failed to fetch trackers list. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")


#
#   MAIN SCRIPT
#

# Configure the logging settings
logging.basicConfig(filename=LOG_FILE,
                    level=logging.INFO, format='%(asctime)s - %(message)s')

# Clear the log file at the start of the script
with open(LOG_FILE, 'w'):
    pass


# Process the trackers list and save all valid URLs and UDP endpoints to a single file
valid_trackers = process_trackers_list(TRACKER_LIST)

if valid_trackers:
    with open(OUTPUT_FILE, "w") as file:
        file.write('\n\n'.join(valid_trackers))
    print(
        f"COMPLETED. {len(valid_trackers)} trackers saved to {OUTPUT_FILE}.")
else:
    print("COMPLETED. No valid trackers were found in the list.")
