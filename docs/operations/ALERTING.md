# Agentic Memories Alerting Configuration

This document provides recommended alert rules and LogQL queries for monitoring Agentic Memories in Grafana Cloud.

## Grafana Cloud Alerts (Free Tier)

Grafana Cloud free tier includes 50 alert rules. The following alerts are recommended for Agentic Memories.

---

## Critical Alerts

These alerts indicate service failures or issues requiring immediate attention.

| Alert Name | LogQL Query | Condition | Notification |
|------------|-------------|-----------|--------------|
| Service Error Spike | `sum(count_over_time({project="agentic-memories"} \|= "ERROR" [5m]))` | > 10 | Email |
| API Health Check Failed | `{service="api"} \|= "health" \|= "failed"` | > 0 | Email |
| Redis Connection Lost | `{project="agentic-memories"} \|= "redis" \|= "connection" \|= "error"` | > 0 | Email |
| Container Restart | `{project="agentic-memories"} \|= "container" \|= "restart"` | > 0 | Email |
| ChromaDB Connection Failed | `{service="api"} \|= "ChromaDB" \|= "error"` | > 0 | Email |

---

## Warning Alerts

These alerts indicate degraded performance or elevated error rates.

| Alert Name | LogQL Query | Condition | Notification |
|------------|-------------|-----------|--------------|
| LLM Latency High | `{service="api"} \| json \| duration_ms > 5000` | > 5/hour | Email |
| Memory Store Failures | `{service="api"} \|= "store" \|= "failed"` | > 3/hour | Email |
| Extraction Errors | `{service="api"} \|= "extraction" \|= "error"` | > 3/hour | Email |
| Rate Limit Warnings | `{project="agentic-memories"} \|= "rate_limit"` | > 1 | Email |

---

## Cost Monitoring Alerts

These alerts help monitor usage and prevent unexpected costs.

| Alert Name | LogQL Query | Condition | Notification |
|------------|-------------|-----------|--------------|
| OpenAI API Calls High | `{service="api"} \| json \| event="openai_call"` | > 1000/day | Email |
| High Log Volume | Use Grafana Cloud usage dashboard | > 40GB/month | Email |

---

## Setting Up Alerts in Grafana Cloud

### Step 1: Access Alerting

1. Log in to [Grafana Cloud](https://grafana.com)
2. Navigate to your stack
3. Click **Alerting** in the left sidebar
4. Click **Alert Rules**

### Step 2: Create New Alert Rule

1. Click **New Alert Rule**
2. Enter a descriptive name (e.g., "Agentic Memories - Service Error Spike")
3. Select **Grafana managed alert**

### Step 3: Configure Query

1. Select your Loki data source (usually named `grafanacloud-<your-stack>-logs`)
2. Enter the LogQL query from the tables above
3. Set the query type to **Range** for aggregations or **Instant** for presence checks

### Step 4: Set Condition

1. In the **Expressions** section, add a **Threshold** condition
2. Set the operator (e.g., `>` for "greater than")
3. Enter the threshold value from the tables above

### Step 5: Configure Evaluation

1. Set **Evaluation interval** to `1m` (1 minute)
2. Set **For** duration to `0s` for immediate alerts or `5m` for sustained conditions

### Step 6: Add Labels and Annotations

```yaml
labels:
  severity: critical  # or warning
  service: agentic-memories

annotations:
  summary: "{{ $labels.alertname }} triggered"
  description: "Alert condition met for Agentic Memories"
```

### Step 7: Configure Notification

1. Go to **Alerting** → **Contact points**
2. Ensure email notification is configured (free tier)
3. Link the contact point to your alert rule

---

## Example Alert Rule (YAML Export)

This YAML can be imported into Grafana Cloud for automation:

```yaml
apiVersion: 1
groups:
  - name: agentic-memories-critical
    folder: AgenticMemories
    interval: 1m
    rules:
      - title: Service Error Spike
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: grafanacloud-logs
            model:
              expr: sum(count_over_time({project="agentic-memories"} |= "ERROR" [5m]))
              queryType: range
          - refId: C
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: __expr__
            model:
              conditions:
                - evaluator:
                    params: [10]
                    type: gt
              type: threshold
        for: 0s
        labels:
          severity: critical
        annotations:
          summary: High error rate detected in Agentic Memories services
          description: More than 10 errors logged in the past 5 minutes
```

---

## Useful LogQL Queries

### View All Errors

```logql
{project="agentic-memories"} |= "ERROR"
```

### Filter by Service

```logql
{service="api", project="agentic-memories"}
```

### API Requests by Endpoint

```logql
{service="api"} | json | line_format "{{.method}} {{.path}} - {{.status}}"
```

### Memory Operations

```logql
{service="api"} |= "memory" | json
```

### Profile Extraction Events

```logql
{service="api"} |= "extraction" | json
```

### ChromaDB Operations

```logql
{service="api"} |= "chroma" | json
```

### Redis Operations

```logql
{service="redis"} | json
```

### Slow Requests (> 2 seconds)

```logql
{service="api"} | json | duration_ms > 2000
```

### Scheduled Intents Activity

```logql
{service="api"} |= "intent" | json
```

---

## Troubleshooting

### Logs Not Appearing in Grafana

1. Verify LOKI_URL is correctly set in `.env`
2. Check network connectivity to Grafana Cloud
3. Verify Loki plugin is installed: `docker plugin ls`
4. Check container logs for driver errors:
   ```bash
   docker inspect <container> | jq '.[0].HostConfig.LogConfig'
   ```

### Alert Not Triggering

1. Test the LogQL query in **Explore** → **Loki**
2. Check alert rule evaluation interval
3. Verify contact point is correctly configured
4. Check Grafana Cloud alerting service status

---

## References

- [Grafana Loki LogQL Documentation](https://grafana.com/docs/loki/latest/logql/)
- [Grafana Alerting Documentation](https://grafana.com/docs/grafana/latest/alerting/)
- [Loki Docker Driver](https://grafana.com/docs/loki/latest/clients/docker-driver/)
- [Grafana Cloud Free Tier Limits](https://grafana.com/docs/grafana-cloud/cost-management-and-billing/understand-your-invoice/usage-limits/)
