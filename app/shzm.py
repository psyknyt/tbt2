import requests
from datetime import datetime

URL = "http://localhost:8000/shazam"

try:
    response = requests.get(URL)
    response.raise_for_status()

    with open("api_log.txt", "a") as f:
        f.write(f"{datetime.now()} : SUCCESS : {response.status_code}\n")

except Exception as e:
    with open("api_log.txt", "a") as f:
        f.write(f"{datetime.now()} : FAILED : {e}\n")