import requests

def fetch_uid_repo(microservice_url):
    response = requests.get(f"{microservice_url}/api/uid-repo/")
    if response.status_code == 200:
        return response.json()  # Return the UID data
    else:
        raise Exception("Failed to fetch UID repo")