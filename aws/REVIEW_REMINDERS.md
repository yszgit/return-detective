# Future review email reminders

## What was missing

The original Future review plan stored an appointment with `email_delivery=NOT_ENABLED`.
No scheduled job existed, so reaching that time could not send an email. Immediate
new-case SNS alerts were a separate integration.

## Current behavior

In **Live agents (Bedrock)** mode, enable **Email reminder to confirmed SNS
subscribers** when saving a Future review plan. This creates and reads back an
AWS EventBridge Scheduler one-time task. It publishes a reminder to the existing
Standard SNS topic, independent of the browser/application staying open.

- Any valid email can subscribe to SNS; it need not be an AWS login address.
  Its owner must confirm the subscription. This app uses the existing confirmed
  topic subscribers. It does not subscribe new addresses automatically.
- The optional contact email is a note, **not a destination override**. All
  topic subscribers whose subscriptions accept the message receive it. Email
  filter policies must be reviewed before scheduling; the helper refuses an
  unexplained email filter rather than claiming delivery.
- Choose at least one minute in the future. Time zone/DST validation converts
  the appointment to UTC. AWS invokes within the selected minute, and inbox
  delivery may take longer. Workshop resources must still exist at execution.
- A reminder does not run Agents, approve proposals or execute retail actions.
- `SCHEDULED` means AWS accepted and read-back verification matched. It does not
  prove later execution or inbox delivery. `PREPARING`/`UNCONFIRMED` preserve a
  tracked intent after a failure; cancel or save again before relying on it.
- Replacing a reminder cancels the tracked previous task before creating the
  replacement. Cancelling leaves the human appointment saved. Deleting a
  workspace cancels tracked tasks before deleting cases; cancellation failure
  stops deletion. Restore never re-arms emails.
- Scripted and recorded modes cannot request real email schedules. Existing
  schedules continue in AWS until cancelled, even if the UI changes mode.
- The schedule deletes itself after completion. Standard SNS and Scheduler
  retries can cause duplicates; this is not an exactly-once delivery guarantee.

## One-time setup

Use the existing Standard `RD_SNS_TOPIC_ARN` with a confirmed email subscriber.
The app identity needs to list/read the SNS subscriptions and create/read/update/
delete schedules in its dedicated group, plus `iam:PassRole` for the exact
execution role. The setup identity also needs the narrowly scoped IAM/group
creation operations used below.

```sh
python scripts/setup_review_reminders.py
python scripts/setup_review_reminders.py --execute
```

The first command prints the concrete plan without AWS calls. The second creates
`return-detective-reviews` and `return-detective-review-scheduler` when absent.
The execution role trusts Scheduler only for this account and schedule group;
its inline policy allows only `sns:Publish` to the exact existing topic. Existing
different trust/policy documents are not overwritten. No schedules or email are
created by setup.

Copy the printed non-secret values into the ignored `.env` and restart:

```dotenv
RD_SCHEDULER_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/return-detective-review-scheduler
RD_SCHEDULER_GROUP=return-detective-reviews
```

The schedule name derives from case-store identity, namespace and case ID. JSON
workspaces use their absolute case-store path; DynamoDB workspaces share the
same name across team machines. Only tracked tasks are cancelled by deletion.

## Evidence and limits

Offline tests verify UTC targets, explicit opt-in, confirmed recipients,
durable failure state, replacement, cancellation and scoped deletion/restore.
A disabled create/read/delete smoke check passed against the Workshop account
on 2026-10-16 without sending email. Enabled execution and inbox receipt require
a separately authorized end-to-end test; a disabled test is not delivery evidence.

AWS references: [email confirmation](https://docs.aws.amazon.com/sns/latest/dg/sns-email-notifications.html),
[one-time schedule precision](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html),
[universal SNS Publish target](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-targets-universal.html),
[execution-role trust scope](https://docs.aws.amazon.com/scheduler/latest/UserGuide/cross-service-confused-deputy-prevention.html).
