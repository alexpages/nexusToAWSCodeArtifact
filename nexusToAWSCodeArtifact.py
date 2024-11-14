import os
import requests
import boto3
from requests.auth import HTTPBasicAuth
import urllib3
import subprocess
import traceback
import concurrent.futures
import shutil

# DESCRIPTION
# ========================================================================================

# This script migrates artifacts from Nexus to AWS CodeArtifact.
#
# Nexus Repository Structure:
#   - Repositories: AAA, BBB
#   - Group IDs: com.XXX.YYY, com.XXX.ZZZ
#   - File Types: .jar, .pom
#
# Preconditions:
#   - AWS CLI installed and configured with necessary permissions
#   - Python 3.8+ installed
#   - Maven installed
#   - PRO tunneling to Nexus server activated in case you need it
#
# Execution Steps:
#   1. Update the variables NEXUS_REPO and NEXUS_GROUP_ID accordingly.
#   2. Run the script using the command: python3 nexusToAwsCodeArtifact.py or through your IDE.
#
# Execution Scenarios:
#   - Run it 2 times, cancel the first one after it stops logging in case it does not stop automatically (it has a 300s timeout per thread). The second execution will finish and clean up temporary files.

# VARIABLES
# ========================================================================================

# Nexus
NEXUS_SERVER_URL = "https://nexus.pro.rpsp.jp"          # Nexus server URL
NEXUS_REPO = "YOUR_NEXUS_REPO"                          # Nexus repository 
NEXUS_USER = "YOUR_NEXUS_USER"                          # Nexus username
NEXUS_PASSWORD = "YOUR_NEXUS_PASSWORD"                  # Nexus password
NEXUS_GROUP_ID = "YOUR_NEXUS_GROUP_ID"                  # Nexus group ID. Is the namespace in AWS
FILE_FILTERS = [".jar", ".pom"]                         # File types to filter

# AWS
AWS_DOMAIN = "YOUR_AWS_DOMAIN"                          # AWS domain
AWS_DOMAIN_OWNER = "YOUR_AWS_DOMAIN_OWNER"              # AWS domain owner ID
AWS_REGION = "ap-northeast-1"                           # AWS region
AWS_REPO = "YOUR_AWS_REPO"                              # AWS repository
AWS_PROFILE = "YOUR_PROFILE"                            # AWS profile (you can set a profile that has the necessary permissions)

# General settings 
PROXIES = {                             
    'http': 'socks5h://127.0.0.1:8888',                 # For PRO tunneling if needed. You can remove it
    'https': 'socks5h://127.0.0.1:8888'
}
TEMP_DIR = "./Desktop/temp"
LOG_FILE = f"{NEXUS_REPO}-log_file.log"
OUTPUT_FILE = f"{NEXUS_REPO}-artifacts.txt"
open(LOG_FILE, 'w').close()
open(OUTPUT_FILE, 'w').close()

session = boto3.Session(profile_name=AWS_PROFILE)
client = session.client('codeartifact', region_name=AWS_REGION, verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# METHODS
# ========================================================================================

def log_message(message, tag="INFO"):
    formatted_message = f"[{tag}] {message}"
    with open(LOG_FILE, 'a') as f:
        f.write(formatted_message + "\n")
    print(formatted_message)


def list_nexus_artifacts():
    log_message(f"Listing all artifacts in Nexus repository {NEXUS_REPO}...", tag="NEXUS")
    continuation_token = ""
    artifacts = []
    while True:
        url = f"{NEXUS_SERVER_URL}/service/rest/v1/components?repository={NEXUS_REPO}"
        if continuation_token:
            url += f"&continuationToken={continuation_token}"
        log_message(f"Fetching URL: {url}", tag="NEXUS")
        response = requests.get(url, headers={'Accept': 'application/json'},
                                verify=False, proxies=PROXIES,
                                auth=HTTPBasicAuth(NEXUS_USER, NEXUS_PASSWORD))
        response.raise_for_status()
        data = response.json()
        for item in data['items']:
            if item['group'].startswith(NEXUS_GROUP_ID.replace('/', '.')):
                for asset in item['assets']:
                    download_url = asset['downloadUrl']
                    if any(download_url.endswith(filter) for filter in FILE_FILTERS):
                        artifacts.append(download_url)
        continuation_token = data.get('continuationToken')
        if not continuation_token:
            break
    return artifacts

def download_single_artifact(url, current, total):
    try:
        url = url.strip()
        response = requests.get(url, auth=HTTPBasicAuth(NEXUS_USER, NEXUS_PASSWORD), verify=False, proxies=PROXIES)
        response.raise_for_status()
        path = url.split(NEXUS_SERVER_URL)[-1].lstrip('/')
        dir_path = os.path.join(TEMP_DIR, os.path.dirname(path))
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, os.path.basename(path))
        with open(file_path, 'wb') as f:
            f.write(response.content)
        log_message(f"[{current}/{total}] Downloaded artifact from URL: {url} to: {file_path}", tag="DOWNLOAD")
        return file_path
    except Exception as e:
        log_message(f"[ERROR]: Failed to download artifact: {url} with error: {e}", tag="MAIN")

def upload_artifact_to_aws_maven(file_path, artifact_id, version, packaging="jar", pom_file=None):
    try:
        cmd = [
            "mvn", "-X", "-e", "deploy:deploy-file",
            f"-Dfile={file_path}",
            f"-DgroupId={NEXUS_GROUP_ID}",
            f"-DartifactId={artifact_id}",
            f"-Dversion={version}",
            f"-Dpackaging={packaging}",
            f"-DrepositoryId=codeartifact",
            f"-Durl=https://{AWS_DOMAIN}-{AWS_DOMAIN_OWNER}.d.codeartifact.{AWS_REGION}.amazonaws.com/maven/{AWS_REPO}/",
            f"-Dmaven.resolver.transport=wagon",
            f"-Dhttps.protocols=TLSv1.2",
            f"-Dmaven.wagon.http.ssl.insecure=true",
            f"-Dmaven.wagon.http.ssl.allowall=true"
        ]
        if pom_file:
            cmd.append(f"-DpomFile={pom_file}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise Exception(f"Command failed with return code {result.returncode}")
        log_message(f"Successfully uploaded {artifact_id}:{version} to AWS CodeArtifact", tag="UPLOAD")
    except Exception as e:
        log_message(f"[ERROR]: Failed to upload {artifact_id}:{version} with error: {e}\n{traceback.format_exc()}", tag="UPLOAD")

def is_package_and_version_published(artifact_id, version, repo):
    try:
        client.describe_package_version(
            domain=AWS_DOMAIN,
            domainOwner=AWS_DOMAIN_OWNER,
            repository=repo,
            format='maven',
            namespace=NEXUS_GROUP_ID,
            package=artifact_id,
            packageVersion=version
        )
        return True
    except client.exceptions.ResourceNotFoundException:
        return False

def update_package_versions_status():
    log_message("Checking for any issues...", tag="MAIN")
    for artifact_id, version in processed_artifacts:
        try:
            response = client.describe_package_version(
                domain=AWS_DOMAIN,
                domainOwner=AWS_DOMAIN_OWNER,
                repository=AWS_REPO,
                format='maven',
                namespace=NEXUS_GROUP_ID,
                package=artifact_id,
                packageVersion=version
            )
            status = response['packageVersion']['status']
            if status in ['Unfinished']:
                client.update_package_versions_status(
                    domain=AWS_DOMAIN,
                    domainOwner=AWS_DOMAIN_OWNER,
                    repository=AWS_REPO,
                    format='maven',
                    namespace=NEXUS_GROUP_ID,
                    package=artifact_id,
                    versions=[version],
                    targetStatus='Published'
                )
                log_message(f"Updated {artifact_id}:{version} status from {status} to Published", tag="UPDATE")
        except client.exceptions.ResourceNotFoundException:
            log_message(f"[ERROR]: Package {artifact_id}:{version} not found in repository {AWS_REPO}", tag="UPDATE")
        except Exception as e:
            log_message(f"[ERROR]: Failed to update status for {artifact_id}:{version} with error: {e}", tag="UPDATE")

# MAIN FUNCTION
# ========================================================================================
def main():
    try:
        # Part 1: Download Nexus artifacts for $SOURCE_REPO
        artifacts = list_nexus_artifacts()
        total_artifacts = len(artifacts)
        with open(OUTPUT_FILE, 'w') as f:
            for artifact_url in artifacts:
                f.write(artifact_url + "\n")

        log_message("Downloading artifacts...", tag="MAIN")
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(download_single_artifact, url, i, total_artifacts) for i, url in
                       enumerate(artifacts, start=1)]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Part 2: Upload to AWS CodeArtifact
        os.environ['CODEARTIFACT_AUTH_TOKEN'] = subprocess.check_output(
            ["/opt/homebrew/bin/aws", "codeartifact", "get-authorization-token", "--domain", AWS_DOMAIN,
             "--domain-owner", AWS_DOMAIN_OWNER, "--query", "authorizationToken", "--output", "text", "--profile",
             AWS_PROFILE, "--no-verify-ssl"]
        ).strip().decode('utf-8')
        global processed_artifacts
        processed_artifacts = set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            upload_futures = []
            for root, dirs, files in os.walk(TEMP_DIR):
                for file in files:
                    if any(file.endswith(filter) for filter in FILE_FILTERS):
                        file_path = os.path.join(root, file)
                        try:
                            parts = file_path.split(os.sep)
                            if NEXUS_REPO not in parts:
                                log_message(f"[ERROR]: '{NEXUS_REPO}' is not in list for file: {file_path}", tag="MAIN")
                                continue
                            artifact_id = parts[-3].strip('=')
                            version = parts[-2]

                            related_files = [os.path.join(root, f) for f in files if
                                             f.startswith(artifact_id) and f.endswith(tuple(FILE_FILTERS))]
                            artifact_key = (artifact_id, version)

                            if artifact_key not in processed_artifacts:
                                processed_artifacts.add(artifact_key)
                                main_artifact = next((f for f in related_files if f.endswith(".jar")), None)
                                pom_file = next((f for f in related_files if f.endswith(".pom")), None)
                                if is_package_and_version_published(artifact_id, version, AWS_REPO):
                                    log_message(
                                        f"[INFO]: Artifact {artifact_id}:{version} already exists in AWS CodeArtifact",
                                        tag="UPLOAD")
                                    continue
                                upload_futures.append(executor.submit(upload_artifact_to_aws_maven, main_artifact, artifact_id,
                                                                      version, "jar", pom_file))
                        except Exception as e:
                            log_message(f"[ERROR]: Failed to prepare upload for artifact: {file_path} with error: {e}",
                                        tag="MAIN")
            upload_futures.append(executor.submit(lambda: None))  # Add sentinel value to ensure all futures are processed
            for future in concurrent.futures.as_completed(upload_futures):
                if future.result() is None:  # Check for sentinel value
                    break

        # Part 3: Double check for any issue and change Unfinished projects to Published
        log_message("Checking for any issues...", tag="MAIN")
        update_package_versions_status()
        log_message("Checking has finalized correctly...", tag="MAIN")


    # Clean up temporary directory
        if os.path.exists(TEMP_DIR):
            try:
                shutil.rmtree(TEMP_DIR)
                log_message("Cleaned up temporary files.", tag="MAIN")
            except Exception as e:
                log_message(f"[ERROR]: Failed to clean up temporary files with error: {e}", tag="MAIN")
    except Exception as e:
        log_message(f"[ERROR]: An error occurred in the main function: {e}\n{traceback.format_exc()}", tag="MAIN")


if __name__ == "__main__":
    main()