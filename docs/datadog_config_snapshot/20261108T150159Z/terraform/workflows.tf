resource "datadog_workflow_automation" "workflow_1" {
  name = "SMIOT | Ca 1 | Refuse restart when samples fresh"
  description = "Ghi quyết định từ chối restart khi mẫu MongoDB còn mới; không thực hiện hành động EC2 hay thiết bị."
  published = true
  tags = ["env:demo","project:smiot","safety:virtual-only","service:smiot-smart-farm"]
  spec_json = <<-JSON
    {
      "handle": "smiot-ca1-refuse-restart",
      "inputSchema": {
        "parameters": [
          {
            "defaultValue": 90,
            "name": "threshold_seconds",
            "type": "NUMBER"
          }
        ]
      },
      "steps": [
        {
          "actionId": "com.datadoghq.dd.metrics.queryScalarData",
          "display": {
            "bounds": {
              "x": 0,
              "y": 96
            }
          },
          "errorHandlers": [
            {
              "fallbackStepName": "Echo_2",
              "retryStrategy": {
                "kind": "RETRY_STRATEGY_LINEAR",
                "linear": {
                  "interval": "1s",
                  "maxRetries": 2
                }
              }
            }
          ],
          "name": "query_freshness_both_sources",
          "outboundEdges": [
            {
              "branchName": "main",
              "nextStepName": "If_condition"
            }
          ],
          "parameters": [
            {
              "name": "range",
              "value": "3m"
            },
            {
              "name": "queries",
              "value": [
                {
                  "aggregator": "last",
                  "data_source": "metrics",
                  "name": "a",
                  "query": "max:smiot.telemetry.sample_age_seconds{farm:greenhouse_a}"
                },
                {
                  "aggregator": "last",
                  "data_source": "metrics",
                  "name": "b",
                  "query": "max:smiot.external.sample_age_seconds{farm:greenhouse_a}"
                }
              ]
            },
            {
              "name": "formulas",
              "value": [
                {
                  "formula": "a"
                },
                {
                  "formula": "b"
                }
              ]
            }
          ]
        },
        {
          "actionId": "com.datadoghq.core.if",
          "display": {
            "bounds": {
              "x": 0,
              "y": 264
            }
          },
          "name": "If_condition",
          "outboundEdges": [
            {
              "branchName": "true",
              "nextStepName": "Echo"
            },
            {
              "branchName": "false",
              "nextStepName": "Echo_1"
            }
          ],
          "parameters": [
            {
              "name": "joinOperator",
              "value": "and"
            },
            {
              "name": "conditions",
              "value": [
                {
                  "comparisonOperator": "eq",
                  "leftValue": "${ (() => { const cols=Steps.query_freshness_both_sources.data?.attributes?.columns || []; const a=cols.find(c=>c.name===\"a\")?.values?.[0]; const b=cols.find(c=>c.name===\"b\")?.values?.[0]; return typeof a===\"number\" && Number.isFinite(a) && a<Trigger.threshold_seconds && typeof b===\"number\" && Number.isFinite(b) && b<Trigger.threshold_seconds; })() }",
                  "rightValue": true
                }
              ]
            }
          ]
        },
        {
          "actionId": "com.datadoghq.core.echo",
          "display": {
            "bounds": {
              "x": 0,
              "y": 432
            }
          },
          "name": "Echo",
          "parameters": [
            {
              "name": "value",
              "value": "${ \"REFUSED_RESTART | CA1 | synthetic demo | worst_node_age_s=\" + Steps.query_freshness_both_sources.data.attributes.columns[0].values[0] + \" | external_farm_age_s=\" + Steps.query_freshness_both_sources.data.attributes.columns[1].values[0] + \" | threshold=\" + Trigger.threshold_seconds + \" | no EC2/device action\" }"
            }
          ]
        },
        {
          "actionId": "com.datadoghq.core.echo",
          "display": {
            "bounds": {
              "x": 384,
              "y": 432
            }
          },
          "name": "Echo_1",
          "parameters": [
            {
              "name": "value",
              "value": "${ \"ESCALATE_HUMAN | CA1 | samples not confirmed fresh | A=\" + (Steps.query_freshness_both_sources.data?.attributes?.columns?.[0]?.values?.[0] ?? \"missing\") + \" B=\" + (Steps.query_freshness_both_sources.data?.attributes?.columns?.[1]?.values?.[0] ?? \"missing\") + \" | no automatic restart\" }"
            }
          ]
        },
        {
          "actionId": "com.datadoghq.core.echo",
          "display": {
            "bounds": {
              "x": 384,
              "y": 264
            }
          },
          "name": "Echo_2",
          "parameters": [
            {
              "name": "value",
              "value": "ESCALATE_HUMAN | CA1 | metric query failed; samples not confirmed fresh | no automatic restart"
            }
          ]
        }
      ],
      "triggers": [
        {
          "monitorTrigger": {
            "rateLimit": {
              "count": 1,
              "interval": "300s"
            }
          },
          "startStepNames": [
            "query_freshness_both_sources"
          ]
        },
        {
          "agentTrigger": {},
          "startStepNames": [
            "query_freshness_both_sources"
          ]
        }
      ]
    }
    JSON
}

resource "datadog_workflow_automation" "workflow_2" {
  name = "SMIOT EC2 Guarded Web Recovery"
  description = "Restart smiot.service only when the local health check fails; verify HTTP recovery and enforce a cooldown."
  published = true
  tags = []
  spec_json = <<-JSON
    {
      "connectionEnvs": [
        {
          "connections": [
            {
              "connectionId": "connection:execgroup_ddagent:i-00bf2d3591d3ee0a2",
              "label": "INTEGRATION_SCRIPT"
            }
          ],
          "env": "default"
        }
      ],
      "handle": "Dũng-Nov-04-2026-1601",
      "steps": [
        {
          "actionId": "com.datadoghq.script.runPredefinedScript",
          "connectionLabel": "INTEGRATION_SCRIPT",
          "display": {
            "bounds": {
              "x": -2.842170943040401e-14,
              "y": -2.4868995751603507e-14
            }
          },
          "name": "Run_Predefined_Script",
          "parameters": [
            {
              "name": "scriptName",
              "value": "recover-smiot-web"
            },
            {
              "name": "timeout",
              "value": 300
            }
          ]
        }
      ],
      "triggers": [
        {
          "monitorTrigger": {
            "rateLimit": {
              "count": 1,
              "interval": "60s"
            }
          },
          "startStepNames": [
            "Run_Predefined_Script"
          ]
        }
      ]
    }
    JSON
}

resource "datadog_workflow_automation" "workflow_3" {
  name = "SMIOT Node 2 Safe Mode - Hold and Verify"
  description = "Rate-limited monitor-triggered safety workflow. The EC2 bridge verifies the monitor and emits only a virtual Wokwi HOLD; there is no physical pump or PLC command."
  published = true
  tags = ["env:demo","project:smiot","safety:virtual-only","service:smiot-smart-farm"]
  spec_json = <<-JSON
    {
      "handle": "smiot-node-2-safe-mode-hold-and-verify",
      "steps": [
        {
          "actionId": "com.datadoghq.http.request",
          "name": "Make_request",
          "parameters": [
            {
              "name": "verb",
              "value": "POST"
            },
            {
              "name": "url",
              "value": "https://13-238-30-218.sslip.io/api/internal/safe-mode/recovery-clear"
            },
            {
              "name": "requestHeaders",
              "value": [
                {
                  "key": "Authorization",
                  "value": [
                    "Bearer <REDACTED_TOKEN>"
                  ]
                }
              ]
            }
          ]
        }
      ],
      "triggers": [
        {
          "monitorTrigger": {
            "rateLimit": {
              "count": 1,
              "interval": "60s"
            }
          },
          "startStepNames": [
            "Make_request"
          ]
        }
      ]
    }
    JSON
}
