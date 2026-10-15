import sys

from .config import aws_settings


def main():
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        print("Install requirements.txt in your project environment first.")
        return 1
    try:
        region, model_id = aws_settings()
        session = boto3.Session(region_name=region)
        identity = session.client("sts").get_caller_identity()
        print(f"AWS identity verified. Account: {identity['Account']}; region: {region}")
        response = session.client("bedrock-runtime").converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "Reply: Return Detective connected."}]}],
            inferenceConfig={"maxTokens": 32},
        )
        print("Bedrock call succeeded:")
        for block in response["output"]["message"]["content"]:
            if "text" in block:
                print(block["text"])
        return 0
    except (ValueError, BotoCoreError, ClientError) as error:
        code = (error.response.get("Error", {}).get("Code", type(error).__name__)
                if isinstance(error, ClientError) else type(error).__name__)
        print(f"AWS check failed: {code}. See docs/AWS_SETUP.md; never share credentials.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
