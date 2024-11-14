#!/bin/bash
 
# Check if profile name is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <profile-name>"
  exit 1
fi
 
PROFILE=$1
TEMP_PROFILE="temporary-session"
ROLE_NAME="YOUR_ROLE"                       # change this
SESSION_EXPIRY="3600"                       # 1h
DEFAULT_REGION="ap-northeast-1"             # change this
 
# Define role ARN based on profile
case $PROFILE in
  dev)
    ROLE_ARN="arn:aws:iam::YOUR_DOMAIN_OWNER:role/$ROLE_NAME"
    ;;
  *)
    echo "Unknown profile: $PROFILE"
    exit 1
    ;;
esac
 
# Assume the role and capture the output
OUTPUT=$(aws sts assume-role --role-arn $ROLE_ARN --role-session-name MySession --duration-seconds $SESSION_EXPIRY --profile $PROFILE --no-verify-ssl)
 
# Extract the credentials
AWS_ACCESS_KEY_ID=$(echo $OUTPUT | jq -r '.Credentials.AccessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo $OUTPUT | jq -r '.Credentials.SecretAccessKey')
AWS_SESSION_TOKEN=$(echo $OUTPUT | jq -r '.Credentials.SessionToken')
 
# Configure the temporary-session profile
aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID --profile $TEMP_PROFILE
aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY --profile $TEMP_PROFILE
aws configure set aws_session_token $AWS_SESSION_TOKEN --profile $TEMP_PROFILE
aws configure set region $DEFAULT_REGION --profile $TEMP_PROFILE
 
echo ""
echo "Temporary credentials set for profile $TEMP_PROFILE."
echo "Default region set to $DEFAULT_REGION for profile $TEMP_PROFILE."
echo "Please use \"--profile $TEMP_PROFILE\" on your next AWS CLI commands."
echo "Please use \"--no-verify-ssl\" if you are running locally on MAC pc."