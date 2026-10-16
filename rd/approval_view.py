"""Explain recorded approval state without creating or authorizing proposals."""


def approval_notice(case, approvals):
    mine = [a for a in approvals if a['case_id'] == case['case_id']]
    pending = sum(a['status'] == 'PENDING' for a in mine)
    if pending:
        return 'info', f'{pending} proposals are waiting for a human decision.'
    if mine:
        approved = sum(a['status'] == 'APPROVED' for a in mine)
        rejected = sum(a['status'] == 'REJECTED' for a in mine)
        return 'info', (f'No pending approvals: {approved} approved and {rejected} rejected proposals. '
                        'See Actions and decisions for the recorded history.')
    if case.get('workflow_error') or not case.get('root_cause'):
        return 'warning', ('No approval request has been recorded. The investigation is incomplete or interrupted; '
                           'review its status and tool results before treating the response as complete.')
    confidence, category = case.get('confidence'), case.get('category', '')
    if confidence == 'Low':
        return 'info', ('No approval request recorded. Investigator confidence is Low. The playbook requires higher '
                        'confidence for action proposals; gather the missing evidence and follow up. See Owner briefing for the next steps.')
    if category == 'Quality' and confidence != 'High':
        return 'info', ('No approval request recorded. Stock holds, supplier claims and proactive outreach require a Quality '
                        'case with High confidence. Review the owner briefing and any fee-tool result for the actions taken or withheld.')
    if confidence in ('Medium', 'High') and (category.startswith('Fit') or category == 'Expectation gap'):
        return 'warning', ('No approval request recorded, although the category and confidence permit a fit-guidance '
                           'proposal. Check the Response Agent tool results and Owner briefing; a recommendation alone is not a saved approval request.')
    if category == 'Quality' and confidence == 'High':
        return 'warning', ('No approval request recorded for this High-confidence Quality case. Check the Response Agent '
                           'tool results and Owner briefing for missing or refused proposals.')
    return 'info', ('No human approval request recorded. Review the owner briefing for evidence requests, monitoring '
                    'or actions within authority. An investigation does not always produce an approval proposal.')
