"""Campaign orchestration (SIP-0109): the campaign object, its lifecycle and its control log.

A campaign is a persisted, resumable state machine that launches cycles. Its state lives behind
``CampaignRegistryPort``, and every control operation is a control-log transition written in the
same transaction as the state change it records (§13). Launches cross into the cycle registry
through launch intents, so each decision launches exactly once (§12b).
"""
