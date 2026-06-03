"""
Webhook-related schemas (Twilio inbound).

Twilio posts ``application/x-www-form-urlencoded``; the handler parses
`MessageSid`, `From`, `To`, `Body`, etc.  No shared Pydantic envelope is
required for the public API — validation is done in the route.
"""
