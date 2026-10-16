"""Check AWS configuration; Bedrock is called only with explicit model-check flags."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def check_identity(region):
    import boto3
    identity = boto3.client('sts', region_name=region).get_caller_identity()
    print(f"PASS identity: account {identity['Account']}, region {region}")


def check_athena():
    from rd import data
    result = data._rows_athena('select count(*) as n from returns')
    print(f"PASS Athena: {result[0]['n']:,} return records in {data.ATHENA_DB}")


def check_model():
    from strands import Agent
    from rd.agents import _model
    result = str(Agent(model=_model(), callback_handler=None)('Reply with exactly: Bedrock OK')).strip()
    if not result:
        raise ValueError('The configured model returned no response.')
    print('PASS Bedrock: configured model responded')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region', help='Workshop region; overrides the local configuration')
    parser.add_argument('--model-only', action='store_true', help='skip Athena and make one explicit Bedrock check')
    parser.add_argument('--allow-model-call', action='store_true', help='also check Bedrock; incurs model usage')
    args = parser.parse_args(argv)
    if args.region:
        os.environ['AWS_REGION'] = args.region
    from rd import config  # Load the local .env after parsing --help/region.
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if not region:
        print('FAIL configuration: set AWS_REGION to the Workshop region, or use --region.')
        return 1
    if (args.model_only or args.allow_model_call) and not os.environ.get('RD_MODEL_ID', '').strip():
        print('FAIL configuration: set RD_MODEL_ID to a permitted Bedrock model or inference profile.')
        return 1
    try:
        check_identity(region)
        if not args.model_only:
            check_athena()
        if args.model_only or args.allow_model_call:
            check_model()
        else:
            print('SKIP Bedrock: use --model-only or --allow-model-call to authorize a model check.')
    except Exception as exc:
        code = getattr(exc, 'response', {}).get('Error', {}).get('Code') or type(exc).__name__
        print(f'FAIL AWS check: {code}')
        print('Check region, unexpired Workshop credentials and resource permissions. See docs/AWS_SETUP.md.')
        print('Share only this status output; never share credentials.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
