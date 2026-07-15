# Durable order submission service

`DurableOrderSubmissionService` owns the submission sequence shared by all
strategies: assign correlation IDs, durably persist an intent, send orders to
the broker, then persist outcomes. If intent persistence fails, no broker call
is made. If outcome persistence fails after a broker call, the existing intent
remains available for recovery policy to block an unsafe automatic retry.
