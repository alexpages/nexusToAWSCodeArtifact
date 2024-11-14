# Nexus to AWS CodeArtifact Migration Script
This script migrates maven artifacts from Nexus to AWS CodeArtifact.

## Nexus Repository Structure
- **Repositories**: AAA, BBB
- **Group IDs**: com.XXX.YYY, com.XXX.ZZZ
- **File Types**: .jar, .pom

## Preconditions
Before running the script, ensure the following are installed and configured:

- AWS CLI installed and configured with necessary permissions
- Python 3.8+ installed
- Maven installed
- PRO tunneling to Nexus server activated if needed

## Execution Steps
1. Update both `NEXUS` and `AWS` variables from `nexusToAWSCodeArtifact.py` script according to your needs, including the region.
2. Update any necessary variables on `assume_role.sh`.
3. I suggest using `assume_role.sh` script. If you do so, after modifying the variables execute `./assume_role.sh dev`. If not, proceed to modify the `nexusToAWSCodeArtifact.py` script to addapt your needs.
5. Finally, run the script through your IDE (IntelliJ with Python Console plugin or VSCode with python plugin) or using the following command: 
   ```
   sh python3 nexusToAwsCodeArtifact.py
   ```

## Execution Scenarios
You should be fine with running the script once. However, since it has checking methods, I suggest you to run it twice and you will get more information throught logs.

## Key points
- This script is done considering that I have another script `assume_role.sh` that creates a profile as temporary session with the token. Thats why you will see often using `AWS_PROFILE` and `--no-verify-ssl`. You can change that and hardcode your AWS CodeArtifact Authentication Token. If you want to use the `assume_role.sh` script, change AWS_PROFILE to `temporary-session`

- To upload to AWSCodeArtifact you will need a AWS Token. Modify the following part in case you don't want to NOT verify ssl or to hardcode your AWS Authentication token
```
os.environ['CODEARTIFACT_AUTH_TOKEN'] = subprocess.check_output(
            ["/opt/homebrew/bin/aws", "codeartifact", "get-authorization-token", "--domain", AWS_DOMAIN,
             "--domain-owner", AWS_DOMAIN_OWNER, "--query", "authorizationToken", "--output", "text", "--profile",
             AWS_PROFILE, "--no-verify-ssl"]
```
- boto3 is being used for opening a sesion and stablishing the client. It uses a AWS_Profile. However, you can modify the session according to your needs.

```
session = boto3.Session(profile_name=AWS_PROFILE)
client = session.client('codeartifact', region_name=AWS_REGION, verify=False)
```
- It uses multithreading to make it faster. Feel free to change the `max_workers` to a number it suits your machine. Or you can remove the multithreading:
```
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
```

## Additional Information
- Ensure you have the necessary permissions to access both Nexus and AWS CodeArtifact.
- For any issues or questions, please refer to the documentation or open an issue on this repository.
