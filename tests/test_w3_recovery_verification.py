"""Focused, offline tests for the W3 SSM completion verifier contract."""

import json
import unittest

from service.w3_recovery_verification import (
    classify_live_health,
    classify_ssm_invocation,
    find_unique_command,
    parse_guard_result,
    validate_instance_id,
    validate_workflow_run_id,
)


class W3RecoveryVerificationTests(unittest.TestCase):
    run_id = "12345678-1234-1234-1234-123456789abc"
    command_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    instance_id = "i-00bf2d3591d3ee0a2"

    def classify(self, invocation, *, run_id=None, command_id=None, instance_id=None):
        return classify_ssm_invocation(
            invocation,
            expected_run_id=self.run_id if run_id is None else run_id,
            expected_command_id=self.command_id if command_id is None else command_id,
            expected_instance_id=self.instance_id if instance_id is None else instance_id,
        )

    def invocation(self, **extra):
        return {"CommandId": self.command_id, "InstanceId": self.instance_id, **extra}

    def test_only_uuid_workflow_run_and_configured_instance_are_accepted(self):
        self.assertTrue(validate_workflow_run_id("12345678-1234-1234-1234-123456789abc"))
        self.assertFalse(validate_workflow_run_id("not-a-workflow-run"))
        self.assertTrue(validate_instance_id("i-00bf2d3591d3ee0a2", "i-00bf2d3591d3ee0a2"))
        self.assertFalse(validate_instance_id("i-0123456789abcdef0", "i-00bf2d3591d3ee0a2"))

    def test_command_lookup_matches_document_instance_and_incident_id(self):
        run_id = "12345678-1234-1234-1234-123456789abc"
        command = {
            "CommandId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "DocumentName": "SMIOT-GuardedStartApp",
            "InstanceIds": ["i-00bf2d3591d3ee0a2"],
            "Parameters": {"IncidentId": [run_id]},
        }
        self.assertEqual(find_unique_command([command], run_id, "i-00bf2d3591d3ee0a2"), {
            "status": "matched", "command_id": command["CommandId"],
        })
        wrong_doc = {**command, "DocumentName": "AWS-RunShellScript"}
        self.assertEqual(find_unique_command([wrong_doc], run_id, "i-00bf2d3591d3ee0a2")["status"], "pending")

    def test_command_lookup_fails_closed_on_duplicate_matching_commands(self):
        run_id = "12345678-1234-1234-1234-123456789abc"
        base = {
            "DocumentName": "SMIOT-GuardedStartApp",
            "InstanceIds": ["i-00bf2d3591d3ee0a2"],
            "Parameters": {"IncidentId": [run_id]},
        }
        commands = [
            {**base, "CommandId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
            {**base, "CommandId": "ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee"},
        ]
        self.assertEqual(
            find_unique_command(commands, run_id, "i-00bf2d3591d3ee0a2"),
            {"status": "not_verified", "reason": "multiple_matching_ssm_commands"},
        )

    def test_ssm_in_progress_is_pending_not_recovery(self):
        self.assertEqual(
            self.classify(self.invocation(Status="InProgress")),
            {"status": "pending", "ssm_status": "InProgress", "command_id": self.command_id,
             "instance_id": self.instance_id, "run_id": self.run_id},
        )

    def test_success_requires_guard_verified_json_from_command_output(self):
        guard = {
            "event": "smiot.guarded_recovery",
            "run_id": "20261110T120000Z-123",
            "action": "start",
            "result": "verified",
            "reason": "app_http_and_fresh_mongodb_telemetry",
            "service": "smiot.service",
            "timestamp": "2026-11-10T12:00:00Z",
        }
        guard["run_id"] = self.run_id
        result = self.classify(self.invocation(
            Status="Success", ResponseCode=0,
            StandardOutputContent="noise\n" + json.dumps(guard),
        ))
        self.assertEqual(result["status"], "recovery_action_verified")
        self.assertEqual(result["action"], "start")

    def test_ssm_success_without_guard_proof_does_not_claim_recovery(self):
        result = self.classify(self.invocation(
            Status="Success", ResponseCode=0, StandardOutputContent="command completed",
        ))
        self.assertEqual(result["status"], "not_verified")

    def test_guard_refusal_is_not_recovery(self):
        guard = {"event": "smiot.guarded_recovery", "run_id": "r1", "action": "none",
                 "result": "refused", "reason": "mongodb_not_active"}
        result = parse_guard_result(json.dumps(guard), expected_run_id=self.run_id)
        self.assertEqual(result["status"], "not_verified")

    def test_already_healthy_is_distinct_from_recovery_action(self):
        guard = {"event": "smiot.guarded_recovery", "run_id": self.run_id, "action": "none",
                 "result": "verified_healthy", "reason": "already_healthy"}
        result = self.classify(self.invocation(
            Status="Success", ResponseCode=0, StandardOutputContent=json.dumps(guard),
        ))
        self.assertEqual(result["status"], "already_healthy")

    def test_live_ssm_document_already_active_schema_is_accepted_only_for_same_run(self):
        run_id = "12345678-1234-1234-1234-123456789abc"
        guard = {
            "event": "smiot.guarded_recovery",
            "incident_id": run_id,
            "status": "skipped",
            "detail": "app_already_active",
            "timestamp": "2026-11-10T12:00:00Z",
        }
        result = classify_ssm_invocation({
            "Status": "Success", "ResponseCode": 0, "CommandId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "InstanceId": "i-00bf2d3591d3ee0a2", "StandardOutputContent": json.dumps(guard),
        }, expected_run_id=run_id, expected_command_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
           expected_instance_id="i-00bf2d3591d3ee0a2")
        self.assertEqual(result["status"], "already_healthy")
        self.assertEqual(result["run_id"], run_id)
        self.assertEqual(classify_ssm_invocation({
            "Status": "Success", "ResponseCode": 0, "CommandId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "InstanceId": "i-00bf2d3591d3ee0a2", "StandardOutputContent": json.dumps(guard),
        }, expected_run_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
           expected_command_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
           expected_instance_id="i-00bf2d3591d3ee0a2")["reason"], "guard_run_id_mismatch")

    def test_live_ssm_document_recovered_schema_is_accepted(self):
        run_id = "12345678-1234-1234-1234-123456789abc"
        guard = {
            "event": "smiot.guarded_recovery",
            "incident_id": run_id,
            "status": "recovered",
            "detail": "app_active_http_healthy_mongodb_ping_and_new_fresh_telemetry",
            "timestamp": "2026-11-10T12:00:00Z",
        }
        result = classify_ssm_invocation({
            "Status": "Success", "ResponseCode": 0, "CommandId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "InstanceId": "i-00bf2d3591d3ee0a2", "StandardOutputContent": json.dumps(guard),
        }, expected_run_id=run_id, expected_command_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
           expected_instance_id="i-00bf2d3591d3ee0a2")
        self.assertEqual(result["status"], "recovery_action_verified")
        self.assertEqual(result["action"], "start")

    def test_success_is_unverified_when_command_or_instance_does_not_match(self):
        guard = {"event": "smiot.guarded_recovery", "run_id": self.run_id, "action": "start",
                 "result": "verified"}
        payload = self.invocation(Status="Success", ResponseCode=0, StandardOutputContent=json.dumps(guard))
        self.assertEqual(self.classify({**payload, "CommandId": "ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee"})["reason"],
                         "ssm_command_id_mismatch")
        self.assertEqual(self.classify({**payload, "InstanceId": "i-0123456789abcdef0"})["reason"],
                         "ssm_instance_id_mismatch")

    def test_recovery_is_unverified_without_expected_correlation(self):
        guard = {"event": "smiot.guarded_recovery", "run_id": self.run_id, "action": "start",
                 "result": "verified"}
        result = classify_ssm_invocation(self.invocation(Status="Success", ResponseCode=0,
            StandardOutputContent=json.dumps(guard)), expected_run_id=self.run_id,
            expected_command_id=None, expected_instance_id=self.instance_id)
        self.assertEqual(result["reason"], "expected_command_id_missing_or_invalid")

    def test_live_health_requires_all_dependencies_and_recent_sample(self):
        healthy = {"app": "ok", "mongo": "ok", "mqtt": "ok", "newest_sample_age_seconds": 75}
        self.assertTrue(classify_live_health(healthy))
        self.assertFalse(classify_live_health({**healthy, "mongo": "fail"}))
        self.assertFalse(classify_live_health({**healthy, "newest_sample_age_seconds": 181}))
        self.assertFalse(classify_live_health({**healthy, "newest_sample_age_seconds": None}))


if __name__ == "__main__":
    unittest.main()
