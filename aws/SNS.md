# Immediate case notifications

Create a Standard SNS topic and confirm an internal team email subscription.
Set `RD_SNS_TOPIC_ARN` in the terminal or ignored `.env` file, then restart Streamlit.
The application's AWS identity needs `sns:Publish` on that exact topic:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "sns:Publish",
    "Resource": "arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:YOUR_TOPIC_NAME"
  }]
}
```

After **Start investigation** finishes successfully and saves the case, the UI
workflow publishes its ID, product, issue, owner and pending proposals. Successful
new-case investigations through **Prepared examples** also publish. This is an
internal team alert: without subscription filters, all confirmed topic subscribers
receive it. It does not send directly to the owner name shown in the case.

Scripted and recorded replay modes never send real notifications. Daily scans,
attaching to an existing completed case, and follow-up checks do not send this
new-case alert. CLI runs are not connected to this UI workflow integration.

The **Who should do what** section shows the notification state. `ACCEPTED` means
SNS accepted the publish, not that the email reached an inbox. The message ID is
saved with the case. Notification failure preserves the case and offers a manual
retry. Check the inbox first: a network timeout can occur after SNS accepted a
message. Confirmed publishes are not resent on repeated investigations.

This is a single-process demo safeguard, not exactly-once delivery. Standard SNS
can redeliver. A process interrupted in `PUBLISHING` requires operator inspection,
and concurrent deployments require a transactional outbox or equivalent claim.

This feature is immediate, not a future review reminder. It does not provision
EventBridge schedules, send approval follow-up alerts, or execute retail actions.
Historical case dates remain explicit in the email even though it is sent now.

To verify end to end, restart with a valid AWS session and Topic ARN, choose
**Live agents (Bedrock)**, and investigate a signal with no existing completed
case. Check the case's SNS status and the subscribed inbox. Refreshing the case or
attaching another return must not send another new-case alert.
