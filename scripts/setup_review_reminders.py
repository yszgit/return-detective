"""Prepare the scoped Scheduler execution role. No schedules or emails are created.

Without --execute, print the concrete IAM/group plan only.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def documents(topic, group):
    match = re.fullmatch(r'arn:(aws(?:-us-gov|-cn)?):sns:([a-z0-9-]+):(\d{12}):[A-Za-z0-9_-]+', topic)
    if not match or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', group):
        raise ValueError('Use a Standard SNS topic ARN and a valid schedule group name.')
    partition, region, account = match.groups()
    trust = {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow',
        'Principal': {'Service': 'scheduler.amazonaws.com'}, 'Action': 'sts:AssumeRole',
        'Condition': {'StringEquals': {'aws:SourceAccount': account,
            'aws:SourceArn': f'arn:{partition}:scheduler:{region}:{account}:schedule-group/{group}'}}}]}
    policy = {'Version': '2012-10-17', 'Statement': [
        {'Effect': 'Allow', 'Action': 'sns:Publish', 'Resource': topic}]}
    return region, account, trust, policy


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--topic-arn')
    p.add_argument('--group', default='return-detective-reviews')
    p.add_argument('--role', default='return-detective-review-scheduler')
    p.add_argument('--execute', action='store_true')
    args = p.parse_args(argv)
    from rd import config  # Load the ignored local configuration after parsing help.
    topic = args.topic_arn or os.environ.get('RD_SNS_TOPIC_ARN', '').strip()
    region, account, trust, policy = documents(topic, args.group)
    if not re.fullmatch(r'[A-Za-z0-9_+=,.@-]{1,64}', args.role):
        p.error('Use a valid IAM role name.')
    print(json.dumps({'group': args.group, 'role': args.role, 'trust': trust,
                      'permission': policy, 'execute': args.execute}, indent=2))
    if not args.execute:
        return
    import boto3
    session = boto3.Session(region_name=region)
    if session.client('sts').get_caller_identity()['Account'] != account:
        raise ValueError('The topic account does not match this AWS session.')
    if session.client('sns').get_topic_attributes(TopicArn=topic)['Attributes']['Owner'] != account:
        raise ValueError('The SNS topic is not owned by this account.')
    scheduler = session.client('scheduler')
    try:
        scheduler.get_schedule_group(Name=args.group)
    except scheduler.exceptions.ResourceNotFoundException:
        scheduler.create_schedule_group(Name=args.group, Tags=[{'Key': 'Project', 'Value': 'ReturnDetective'}])
    iam = session.client('iam')
    try:
        role = iam.get_role(RoleName=args.role)['Role']
    except iam.exceptions.NoSuchEntityException:
        role = iam.create_role(RoleName=args.role, AssumeRolePolicyDocument=json.dumps(trust),
            Description='Publish planned Return Detective reviews to the existing team SNS topic only.',
            Tags=[{'Key': 'Project', 'Value': 'ReturnDetective'}])['Role']
    if role['AssumeRolePolicyDocument'] != trust:
        raise ValueError('An existing role has different trust permissions; it was not changed.')
    name = 'PublishReturnDetectiveReviewOnly'
    try:
        current = iam.get_role_policy(RoleName=args.role, PolicyName=name)['PolicyDocument']
    except iam.exceptions.NoSuchEntityException:
        iam.put_role_policy(RoleName=args.role, PolicyName=name, PolicyDocument=json.dumps(policy))
    else:
        if current != policy:
            raise ValueError('An existing policy targets another resource; it was not changed.')
    print('RD_SCHEDULER_ROLE_ARN=' + role['Arn'])
    print('RD_SCHEDULER_GROUP=' + args.group)
    print('Setup verified. No reminder schedule or email has been created.')


if __name__ == '__main__':
    main()
