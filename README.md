# Nexus to AWS CodeArtifact Migration Script

This script migrates Maven artifacts from Nexus to AWS CodeArtifact.

## Nexus Repository Structure

- **Repositories**: AAA, BBB
- **Group IDs**: com.XXX.YYY, com.XXX.ZZZ
- **File Types**: .jar, .pom

## Preconditions

Ensure the following are installed and configured before running the script:

- AWS CLI with necessary permissions
- Python 3.8+
- Maven
- PRO tunneling to Nexus server (if needed)

## Execution Steps

1. Update `NEXUS` and `AWS` variables in `nexusToAWSCodeArtifact.py` according to your needs, including the region.
2. Update necessary variables in `assume_role.sh`.
3. Use `assume_role.sh` script by executing `./assume_role.sh dev` after modifying the variables. Alternatively, modify `nexusToAWSCodeArtifact.py` to suit your needs.
4. Run the script through your IDE (IntelliJ with Python Console plugin or VSCode with Python plugin) or using the command:

   ```sh
   python3 nexusToAwsCodeArtifact.py
   ```

## Execution Scenarios

Running the script once should suffice, but running it twice provides more information through logs.

## Key Points

- The script uses `assume_role.sh` to create a temporary session profile with a token, often using `AWS_PROFILE` and `--no-verify-ssl`. You can hardcode your AWS CodeArtifact Authentication Token if preferred. Change `AWS_PROFILE` to `temporary-session` if using `assume_role.sh`.
- To upload to AWS CodeArtifact, you need an AWS Token. Modify the following part if you don't want to skip SSL verification or hardcode your AWS Authentication token:

   ```python
   os.environ['CODEARTIFACT_AUTH_TOKEN'] = subprocess.check_output(
       ["/opt/homebrew/bin/aws", "codeartifact", "get-authorization-token", "--domain", AWS_DOMAIN,
       "--domain-owner", AWS_DOMAIN_OWNER, "--query", "authorizationToken", "--output", "text", "--profile",
       AWS_PROFILE, "--no-verify-ssl"]
   )
   ```

- `boto3` is used for opening a session and establishing the client. It uses an AWS Profile, but you can modify the session as needed:

   ```python
   session = boto3.Session(profile_name=AWS_PROFILE)
   client = session.client('codeartifact', region_name=AWS_REGION, verify=False)
   ```

- The script uses multithreading to speed up the process. Adjust `max_workers` to suit your machine or remove multithreading:

   ```python
   with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
   ```

## Additional Information

- Ensure you have the necessary permissions to access both Nexus and AWS CodeArtifact.
- For issues or questions, refer to the documentation or open an issue on this repository.
