resource "datadog_dashboard_json" "smiot_farm_operations" {
  dashboard = <<-JSON
    {
      "description": "Live operational view for SMIOT. Telemetry source is currently the Wokwi/synthetic stream; values must not be presented as physical sensor readings.",
      "experienceType": "default",
      "layoutType": "ordered",
      "notifyList": [],
      "reflowType": "auto",
      "restrictedRoles": [],
      "templateVariables": [
        {
          "_default": "greenhouse_a",
          "availableValues": [
            "greenhouse_a",
            "greenhouse_b",
            "greenhouse_c",
            "greenhouse_d"
          ],
          "name": "farm",
          "prefix": "farm"
        }
      ],
      "title": "SMIOT | Farm Operations & Recovery (US)",
      "widgets": [
        {
          "definition": {
            "legendLayout": "horizontal",
            "requests": [
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "avg:smiot.telemetry.soil_humidity{$farm,source:smiot_demo_stream} by {node}"
                  }
                ],
                "responseFormat": "timeseries"
              }
            ],
            "showLegend": true,
            "title": "Soil humidity by node (source-tagged)",
            "type": "timeseries"
          },
          "id": 2374606949439936
        },
        {
          "definition": {
            "legendLayout": "horizontal",
            "requests": [
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "avg:smiot.telemetry.air_temperature{$farm,source:smiot_demo_stream} by {node}"
                  }
                ],
                "responseFormat": "timeseries"
              },
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "avg:smiot.telemetry.air_humidity{$farm,source:smiot_demo_stream} by {node}"
                  }
                ],
                "responseFormat": "timeseries"
              }
            ],
            "showLegend": true,
            "title": "Air temperature & humidity by node",
            "type": "timeseries"
          },
          "id": 8557127470261340
        },
        {
          "definition": {
            "legendLayout": "horizontal",
            "requests": [
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "avg:smiot.telemetry.soil_temperature{$farm,source:smiot_demo_stream} by {node}"
                  }
                ],
                "responseFormat": "timeseries"
              },
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "avg:smiot.telemetry.soil_ec{$farm,source:smiot_demo_stream} by {node}"
                  }
                ],
                "responseFormat": "timeseries"
              },
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "max:smiot.telemetry.sample_age_seconds{$farm,source:smiot_demo_stream} by {node}"
                  }
                ],
                "responseFormat": "timeseries"
              }
            ],
            "showLegend": true,
            "title": "Soil temperature, EC & telemetry freshness",
            "type": "timeseries"
          },
          "id": 6867564343230815
        },
        {
          "definition": {
            "requests": [
              {
                "queries": [
                  {
                    "aggregator": "last",
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "min:smiot.dependency.mongo.up{*}"
                  }
                ],
                "responseFormat": "scalar"
              }
            ],
            "title": "MongoDB dependency",
            "type": "query_value"
          },
          "id": 6099923936607867
        },
        {
          "definition": {
            "requests": [
              {
                "queries": [
                  {
                    "aggregator": "last",
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "min:smiot.dependency.mqtt.up{*}"
                  }
                ],
                "responseFormat": "scalar"
              }
            ],
            "title": "MQTT dependency",
            "type": "query_value"
          },
          "id": 855742527872950
        },
        {
          "definition": {
            "showErrorBudget": true,
            "sloId": "886b6bcadb0157948e6faeba54c8a50b",
            "timeWindows": [
              "7d"
            ],
            "title": "Trusted telemetry availability (7d)",
            "type": "slo",
            "viewMode": "overall",
            "viewType": "detail"
          },
          "id": 123825524949010
        },
        {
          "definition": {
            "legendLayout": "horizontal",
            "requests": [
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "sum:mongodb.queries.count{*} by {database_instance}.as_rate()"
                  }
                ],
                "responseFormat": "timeseries"
              }
            ],
            "showLegend": true,
            "title": "MongoDB DBM — query throughput (queries/sec)",
            "type": "timeseries"
          },
          "id": 5143245376144486
        },
        {
          "definition": {
            "legendLayout": "horizontal",
            "requests": [
              {
                "displayType": "line",
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "sum:mongodb.queries.time{*} by {database_instance}.as_count()"
                  }
                ],
                "responseFormat": "timeseries"
              }
            ],
            "showLegend": true,
            "title": "MongoDB DBM — query execution time (ns per collection interval)",
            "type": "timeseries"
          },
          "id": 2638103142544857
        },
        {
          "definition": {
            "legendColumns": [
              "avg",
              "min",
              "max",
              "value",
              "sum"
            ],
            "legendLayout": "auto",
            "requests": [
              {
                "displayType": "line",
                "formulas": [
                  {
                    "formula": "query1"
                  }
                ],
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "avg:system.cpu.user{host:i-00bf2d3591d3ee0a2}"
                  }
                ],
                "responseFormat": "timeseries",
                "style": {
                  "lineType": "solid",
                  "lineWidth": "normal",
                  "orderBy": "values",
                  "palette": "dog_classic"
                }
              }
            ],
            "showLegend": true,
            "title": "EC2 CPU user (%) - SMIOT host",
            "titleAlign": "left",
            "titleSize": "16",
            "type": "timeseries"
          },
          "id": 3794089552414176
        },
        {
          "definition": {
            "autoscale": true,
            "precision": 1,
            "requests": [
              {
                "conditionalFormats": [],
                "formulas": [
                  {
                    "formula": "query1"
                  }
                ],
                "queries": [
                  {
                    "aggregator": "last",
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "avg:system.mem.pct_usable{host:i-00bf2d3591d3ee0a2}"
                  }
                ],
                "responseFormat": "scalar"
              }
            ],
            "time": {},
            "timeseriesBackground": {
              "type": "area"
            },
            "title": "EC2 RAM usable (percent of total RAM)",
            "titleAlign": "left",
            "titleSize": "16",
            "type": "query_value"
          },
          "id": 7811276658605761
        },
        {
          "definition": {
            "legendColumns": [
              "avg",
              "min",
              "max",
              "value",
              "sum"
            ],
            "legendLayout": "auto",
            "requests": [
              {
                "displayType": "line",
                "formulas": [
                  {
                    "formula": "query1"
                  },
                  {
                    "formula": "query2"
                  },
                  {
                    "formula": "query3"
                  },
                  {
                    "formula": "query4"
                  }
                ],
                "queries": [
                  {
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "sum:mongodb.connections.current{*}"
                  },
                  {
                    "dataSource": "metrics",
                    "name": "query2",
                    "query": "sum:mongodb.opcounters.queryps{*}"
                  },
                  {
                    "dataSource": "metrics",
                    "name": "query3",
                    "query": "sum:mongodb.opcounters.insertps{*}"
                  },
                  {
                    "dataSource": "metrics",
                    "name": "query4",
                    "query": "sum:mongodb.opcounters.updateps{*}"
                  }
                ],
                "responseFormat": "timeseries",
                "style": {
                  "lineType": "solid",
                  "lineWidth": "normal",
                  "orderBy": "values",
                  "palette": "dog_classic"
                }
              }
            ],
            "showLegend": true,
            "title": "MongoDB connections and operations per second",
            "titleAlign": "left",
            "titleSize": "16",
            "type": "timeseries"
          },
          "id": 4727374231518807
        },
        {
          "definition": {
            "autoscale": true,
            "precision": 0,
            "requests": [
              {
                "conditionalFormats": [],
                "formulas": [
                  {
                    "formula": "query1"
                  }
                ],
                "queries": [
                  {
                    "aggregator": "last",
                    "dataSource": "metrics",
                    "name": "query1",
                    "query": "sum:mongodb.stats.storagesize{*}"
                  }
                ],
                "responseFormat": "scalar"
              }
            ],
            "timeseriesBackground": {
              "type": "bars"
            },
            "title": "MongoDB storage size (bytes)",
            "titleAlign": "left",
            "titleSize": "16",
            "type": "query_value"
          },
          "id": 2798058504602215
        }
      ]
    }
    JSON
}
