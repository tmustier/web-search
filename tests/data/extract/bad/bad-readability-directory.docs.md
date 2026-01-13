## All docs topics

* Account settings
* API keys
* Alerts
* Analytics
* Archiving
* Audit logs
* Automation
* Backups
* Batch jobs
* Billing
* Budgets
* Change management
* CLI reference
* Compliance
* Connectors
* Data export
* Data import
* Deployment
* Encryption
* Error handling
* Events
* Feature flags
* Files
* Governance
* Identity
* Incident response
* Integrations
* Latency
* Logs
* Maintenance
* Metrics
* Migration
* Monitoring
* Notifications
* On-call
* Permissions
* Personalization
* Regions
* Retention
* Roles
* Routing
* Runbooks
* Sandboxing
* Scheduling
* Secrets
* Service health
* SLAs
* Storage
* Support
* Task queues
* Telemetry
* Tenancy
* Threat models
* Tracing
* User management
* Webhooks

# Incident Postmortem: Queue Lag on 2026-01-05

On Jan 5, a misconfigured retry policy caused queue lag spikes for
about 32 minutes. We paused worker pools, drained the backlog, and
reprocessed delayed jobs.

**Sponsored:** Download the on-call checklist template.

## What happened

A newly deployed workflow increased retries from 3 to 15. The queue
service auto-scaled, but throttling caused delays in downstream systems.

## Fix

We reverted the change, capped retries, and added alerting for retry
spikes. We also added a dashboard for queue latency percentiles.

## Takeaways

* Retry policies should be reviewed with SRE.
* Alert on queue depth early.
* Document escalation paths for paging.
