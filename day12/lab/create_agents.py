#!/usr/bin/env python3
"""
create_agents.py
Auto-creates all Bedrock resources for Day 12 lab in YOUR AWS account.
Run once after deploy_tools.sh. Takes 5-8 minutes.
Writes SUPERVISOR_AGENT_ID, SUPERVISOR_ALIAS_ID, GUARDRAIL_ID to lab/.env automatically.

Usage (from repo/day12/ directory):
    python lab/create_agents.py
"""

import boto3
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

REGION    = "us-east-1"
MODEL_ID  = "amazon.nova-pro-v1:0"

SCRIPT_DIR = Path(__file__).parent          # repo/day12/lab/
ENV_PATH   = SCRIPT_DIR / ".env"
AGENTS_DIR = SCRIPT_DIR / "agents"

# ── Tool registry ───────────────────────────────────────────────────────────────

TOOLS = {
    "check_cloudwatch_metrics": {
        "lambda": "sigma-tool-check-cloudwatch",
        "description": "Check CloudWatch metrics for Lambda errors, Firehose delivery failures, Kinesis throttles, and Lambda version history.",
        "parameters": {
            "hours_back": {"description": "Hours to look back", "required": True, "type": "integer"},
        },
    },
    "query_snowflake": {
        "lambda": "sigma-tool-query-snowflake",
        "description": "Run a SQL query against Snowflake and return results as JSON.",
        "parameters": {
            "sql": {"description": "SQL query to execute", "required": True, "type": "string"},
        },
    },
    "get_kinesis_records": {
        "lambda": "sigma-tool-get-kinesis-records",
        "description": "Replay records from Kinesis shard from a given timestamp with field remapping applied.",
        "parameters": {
            "start_timestamp": {"description": "ISO timestamp to start replay from", "required": True, "type": "string"},
            "already_loaded_ids": {"description": "Comma-separated transaction_ids already in Snowflake (dedup)", "required": False, "type": "string"},
        },
    },
    "rollback_lambda_version": {
        "lambda": "sigma-tool-rollback-lambda",
        "description": "Roll back a Lambda alias to the previous stable version and verify with test records.",
        "parameters": {
            "function_name": {"description": "Lambda function name", "required": True, "type": "string"},
            "alias_name": {"description": "Lambda alias to update, e.g. LIVE", "required": True, "type": "string"},
            "target_version": {"description": "Version to roll back to, or 'previous' for auto-detect", "required": True, "type": "string"},
        },
    },
    "create_cloudwatch_alarm": {
        "lambda": "sigma-tool-create-alarm",
        "description": "Create a CloudWatch metric alarm in the current AWS account.",
        "parameters": {
            "alarm_type": {"description": "Alarm template to use: zero_snowflake_load | lambda_version_change | pipeline_row_divergence", "required": True, "type": "string"},
            "sns_topic_arn": {"description": "SNS topic ARN for alarm notifications", "required": False, "type": "string"},
        },
    },
    "quarantine_rows": {
        "lambda": "sigma-tool-quarantine-rows",
        "description": "Write rejected records to S3 quarantine/ with a reason tag.",
        "parameters": {
            "records": {"description": "JSON array of records to quarantine", "required": True, "type": "string"},
            "quarantine_reason": {"description": "Reason, e.g. null_transaction_id", "required": True, "type": "string"},
        },
    },
    "load_to_snowflake": {
        "lambda": "sigma-tool-load-snowflake",
        "description": "Bulk load records to Snowflake using MERGE INTO on transaction_id (idempotent).",
        "parameters": {
            "records": {"description": "JSON array of records to load", "required": True, "type": "string"},
        },
    },
    "write_incident_report": {
        "lambda": "sigma-tool-write-report",
        "description": "Write a structured incident post-mortem report to S3 reports/.",
        "parameters": {
            "findings": {"description": "JSON object with all agent findings", "required": True, "type": "string"},
        },
    },
    "send_sns_alert": {
        "lambda": "sigma-tool-send-alert",
        "description": "Publish an alert to the sigma-alerts SNS topic.",
        "parameters": {
            "message": {"description": "Alert message text", "required": True, "type": "string"},
            "severity": {"description": "low / medium / high / critical", "required": True, "type": "string"},
        },
    },
}

AGENT_TOOLS = {
    "ForensicsAgent":      ["check_cloudwatch_metrics", "query_snowflake"],
    "ImpactAgent":         ["query_snowflake"],
    "RecoveryAgent":       ["get_kinesis_records", "query_snowflake", "quarantine_rows", "load_to_snowflake"],
    "RollbackAgent":       ["rollback_lambda_version", "send_sns_alert"],
    "HardeningAgent":      ["create_cloudwatch_alarm", "send_sns_alert"],
    "IncidentReportAgent": ["write_incident_report", "send_sns_alert"],
    "SupervisorAgent":     list(TOOLS.keys()),
}

INSTRUCTION_FILES = {
    "ForensicsAgent":      "forensics_instructions.md",
    "ImpactAgent":         "impact_instructions.md",
    "RecoveryAgent":       "recovery_instructions.md",
    "RollbackAgent":       "rollback_instructions.md",
    "HardeningAgent":      "hardening_instructions.md",
    "IncidentReportAgent": "incident_report_instructions.md",
    "SupervisorAgent":     "supervisor_instructions.md",
}

SUB_AGENTS = [
    "ForensicsAgent", "ImpactAgent", "RecoveryAgent",
    "RollbackAgent",  "HardeningAgent", "IncidentReportAgent",
]

COLLAB_INSTRUCTIONS = {
    "ForensicsAgent":      "Investigate the pipeline failure root cause. Return structured forensics findings: root cause, failure timestamp, and records gap.",
    "ImpactAgent":         "Calculate business impact of the failure. Query Snowflake for GMV gap and check SLA contracts. Return breach status and notification requirement.",
    "RecoveryAgent":       "Replay missing records from Kinesis to Snowflake. Only call AFTER RollbackAgent confirms stable. Return rows loaded and quarantine count.",
    "RollbackAgent":       "Roll back the broken Lambda version. Call BEFORE RecoveryAgent. Return rollback status and whether recovery is cleared to proceed.",
    "HardeningAgent":      "Create 3 CloudWatch alarms based on Forensics findings to prevent recurrence. Return alarm names and creation status.",
    "IncidentReportAgent": "Compile all findings into a CTO-ready post-mortem. Write to S3 and send SNS alert. Return report S3 path.",
}

# ── Dispatcher Lambda source ────────────────────────────────────────────────────
# This Lambda sits between Bedrock agents and the tool Lambdas.
# Bedrock calls this dispatcher; dispatcher calls the correct tool Lambda.

DISPATCHER_SOURCE = '''
import boto3
import json

TOOL_MAP = {
    "check_cloudwatch_metrics": "sigma-tool-check-cloudwatch",
    "query_snowflake":           "sigma-tool-query-snowflake",
    "get_kinesis_records":       "sigma-tool-get-kinesis-records",
    "rollback_lambda_version":   "sigma-tool-rollback-lambda",
    "create_cloudwatch_alarm":   "sigma-tool-create-alarm",
    "quarantine_rows":           "sigma-tool-quarantine-rows",
    "load_to_snowflake":         "sigma-tool-load-snowflake",
    "write_incident_report":     "sigma-tool-write-report",
    "send_sns_alert":            "sigma-tool-send-alert",
}


def lambda_handler(event, context):
    function_name = event.get("function", "")
    parameters    = {p["name"]: p["value"] for p in event.get("parameters", [])}
    action_group  = event.get("actionGroup", "")

    target = TOOL_MAP.get(function_name)
    if not target:
        body = json.dumps({"error": f"Unknown function: {function_name}"})
    else:
        lc   = boto3.client("lambda")
        resp = lc.invoke(FunctionName=target, Payload=json.dumps(parameters))
        body = resp["Payload"].read().decode("utf-8")

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "function": function_name,
            "functionResponse": {
                "responseBody": {"TEXT": {"body": body}}
            },
        },
    }
'''

# ── Helpers ─────────────────────────────────────────────────────────────────────

def log(msg):
    print(msg, flush=True)


def load_env():
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def update_env(updates):
    content = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    for key, val in updates.items():
        pattern = rf"^{re.escape(key)}\s*=.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{key}={val}", content, flags=re.MULTILINE)
        else:
            content = content.rstrip("\n") + f"\n{key}={val}\n"
    ENV_PATH.write_text(content)


def wait_for_agent(client, agent_id, desired, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get_agent(agentId=agent_id)["agent"]["agentStatus"]
        if status == desired:
            return status
        if "FAILED" in status or "DELETE" in status:
            raise RuntimeError(f"Agent {agent_id} in unexpected state: {status}")
        time.sleep(6)
    raise TimeoutError(f"Agent {agent_id} did not reach {desired} within {timeout}s")


def wait_for_agent_stable(client, agent_id, timeout=180):
    stable_statuses = {"NOT_PREPARED", "PREPARED"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get_agent(agentId=agent_id)["agent"]["agentStatus"]
        if status in stable_statuses:
            return status
        if "FAILED" in status or "DELETE" in status:
            raise RuntimeError(f"Agent {agent_id} in unexpected state: {status}")
        time.sleep(6)
    raise TimeoutError(f"Agent {agent_id} did not reach a stable state within {timeout}s")


def prepare_agent_if_needed(client, agent_id):
    status = client.get_agent(agentId=agent_id)["agent"]["agentStatus"]
    if status != "PREPARED":
        client.prepare_agent(agentId=agent_id)
        wait_for_agent(client, agent_id, "PREPARED")
        log("  Prepared.")
    else:
        log("  Already prepared.")


def wait_for_alias(client, agent_id, alias_id, target_version=None, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        alias = client.get_agent_alias(
            agentId=agent_id,
            agentAliasId=alias_id,
        )["agentAlias"]
        status = alias["agentAliasStatus"]
        routed_versions = {
            r.get("agentVersion")
            for r in alias.get("routingConfiguration", [])
        }
        if status == "PREPARED" and (
            target_version is None or target_version in routed_versions
        ):
            return alias
        if status in {"FAILED", "DELETING", "DISSOCIATED"}:
            reasons = ", ".join(alias.get("failureReasons", []))
            raise RuntimeError(
                f"Alias {alias_id} for agent {agent_id} is {status}: {reasons}"
            )
        time.sleep(6)
    raise TimeoutError(f"Alias {alias_id} did not reach PREPARED within {timeout}s")


def get_latest_agent_version(client, agent_id):
    versions = list_agent_versions(client, agent_id)
    non_draft = [
        v for v in versions
        if v["agentVersion"] != "DRAFT"
    ]
    if not non_draft:
        return None
    return str(max(int(v["agentVersion"]) for v in non_draft))


def upsert_agent_alias(client, agent_id, alias_name="v1"):
    latest_version = get_latest_agent_version(client, agent_id)

    alias_id = find_alias(client, agent_id, alias_name)
    if alias_id:
        if latest_version:
            client.update_agent_alias(
                agentId=agent_id,
                agentAliasId=alias_id,
                agentAliasName=alias_name,
                routingConfiguration=[{"agentVersion": latest_version}],
            )
        alias = wait_for_alias(client, agent_id, alias_id, latest_version)
        version_label = latest_version or alias_version_label(alias)
        log(f"  Alias {alias_name}: {alias_id} → version {version_label}")
        return alias_id, alias["agentAliasArn"]

    kwargs = {
        "agentId": agent_id,
        "agentAliasName": alias_name,
    }
    if latest_version:
        kwargs["routingConfiguration"] = [{"agentVersion": latest_version}]

    alias = client.create_agent_alias(**kwargs)["agentAlias"]
    alias_id = alias["agentAliasId"]
    alias = wait_for_alias(client, agent_id, alias_id, latest_version)
    version_label = latest_version or alias_version_label(alias)
    log(f"  Alias {alias_name}: {alias_id} → version {version_label}")
    return alias_id, alias["agentAliasArn"]


def alias_version_label(alias):
    routed_versions = [
        r.get("agentVersion")
        for r in alias.get("routingConfiguration", [])
        if r.get("agentVersion")
    ]
    return ", ".join(routed_versions) if routed_versions else "auto-created"


def list_agent_versions(client, agent_id):
    versions = []
    kwargs = {"agentId": agent_id, "maxResults": 100}
    while True:
        resp = client.list_agent_versions(**kwargs)
        versions.extend(resp.get("agentVersionSummaries", []))
        next_token = resp.get("nextToken")
        if not next_token:
            return versions
        kwargs["nextToken"] = next_token


def find_agent_by_name(client, name):
    kwargs = {"maxResults": 100}
    while True:
        resp = client.list_agents(**kwargs)
        for a in resp.get("agentSummaries", []):
            if a["agentName"] == name:
                return a["agentId"]
        next_token = resp.get("nextToken")
        if not next_token:
            return None
        kwargs["nextToken"] = next_token
    return None


def find_alias(client, agent_id, alias_name):
    kwargs = {"agentId": agent_id, "maxResults": 100}
    while True:
        resp = client.list_agent_aliases(**kwargs)
        for a in resp.get("agentAliasSummaries", []):
            if a["agentAliasName"] == alias_name:
                return a["agentAliasId"]
        next_token = resp.get("nextToken")
        if not next_token:
            return None
        kwargs["nextToken"] = next_token


def build_functions(tool_names):
    functions = []
    for t_name in tool_names:
        t = TOOLS[t_name]
        functions.append({
            "name": t_name,
            "description": t["description"],
            "parameters": {
                p_name: {
                    "description": p["description"],
                    "required": p["required"],
                    "type": p["type"],
                }
                for p_name, p in t["parameters"].items()
            },
        })
    return functions


def role_name_from_arn(role_arn):
    if ":role/" not in role_arn:
        raise ValueError(f"Expected an IAM role ARN, got: {role_arn}")
    return role_arn.split(":role/", 1)[1]


def ensure_bedrock_agent_role_permissions(iam, role_arn, account_id, guardrail_id, dispatcher_arn):
    role_name = role_name_from_arn(role_arn)
    log("\n[IAM] Ensuring Bedrock can assume and use the agent role...")

    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowLambdaAssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            },
            {
                "Sid": "AllowBedrockAssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "bedrock.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {"AWS:SourceArn": f"arn:aws:bedrock:{REGION}:{account_id}:agent/*"},
                },
            },
        ],
    }

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AgentModelInvocation",
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": f"arn:aws:bedrock:{REGION}::foundation-model/{MODEL_ID}",
            },
            {
                "Sid": "AgentGuardrail",
                "Effect": "Allow",
                "Action": ["bedrock:ApplyGuardrail"],
                "Resource": f"arn:aws:bedrock:{REGION}:{account_id}:guardrail/{guardrail_id}",
            },
            {
                "Sid": "AgentMultiAgentCollaboration",
                "Effect": "Allow",
                "Action": ["bedrock:GetAgentAlias", "bedrock:InvokeAgent"],
                "Resource": f"arn:aws:bedrock:{REGION}:{account_id}:agent-alias/*/*",
            },
            {
                "Sid": "AgentActionGroupLambda",
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": dispatcher_arn,
            },
        ],
    }

    try:
        iam.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust),
        )
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="sigma-bedrock-agent-policy",
            PolicyDocument=json.dumps(policy),
        )
    except Exception as e:
        raise RuntimeError(
            "Could not update the IAM role for Bedrock multi-agent collaboration. "
            "Re-run lab/setup_aws.py with IAM permissions, then re-run this script. "
            f"Original error: {e}"
        ) from e

    log("  Bedrock trust and collaborator permissions ready.")
    log("  Waiting 10 seconds for IAM propagation...")
    time.sleep(10)


# ── Step 1: Dispatcher Lambda ───────────────────────────────────────────────────

def deploy_dispatcher(lc, role_arn, account_id):
    func_name = "sigma-bedrock-dispatcher"
    log(f"\n[1/9] Deploying {func_name}...")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("dispatcher.py", DISPATCHER_SOURCE)
    zip_bytes = buf.getvalue()

    try:
        lc.get_function(FunctionName=func_name)
        lc.update_function_code(FunctionName=func_name, ZipFile=zip_bytes)
        log("  Updated.")
    except lc.exceptions.ResourceNotFoundException:
        lc.create_function(
            FunctionName=func_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="dispatcher.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Timeout=120,
            MemorySize=256,
        )
        waiter = lc.get_waiter("function_active")
        waiter.wait(FunctionName=func_name)
        log("  Created.")

    # Allow Bedrock to invoke this Lambda
    try:
        lc.add_permission(
            FunctionName=func_name,
            StatementId="allow-bedrock-invoke",
            Action="lambda:InvokeFunction",
            Principal="bedrock.amazonaws.com",
            SourceAccount=account_id,
        )
    except lc.exceptions.ResourceConflictException:
        pass  # permission already exists

    dispatcher_arn = f"arn:aws:lambda:{REGION}:{account_id}:function:{func_name}"
    log(f"  ARN: {dispatcher_arn}")
    return dispatcher_arn


# ── Step 2: Guardrail ───────────────────────────────────────────────────────────

def get_or_create_guardrail(bedrock):
    log("\n[2/9] Setting up Guardrail...")
    resp = bedrock.list_guardrails(maxResults=100)
    for g in resp.get("guardrails", []):
        if g["name"] == "sigma-platform-guardrail":
            log(f"  Already exists: {g['id']}")
            return g["id"]

    r = bedrock.create_guardrail(
        name="sigma-platform-guardrail",
        description="PII redaction + destructive SQL blocking for Sigma DataTech",
        topicPolicyConfig={
            "topicsConfig": [{
                "name": "destructive-sql",
                "definition": "SQL that destroys or removes data: DROP TABLE, DELETE FROM, TRUNCATE TABLE",
                "examples": ["DROP TABLE transactions", "DELETE FROM SIGMA.SILVER.TRANSACTIONS"],
                "type": "DENY",
            }]
        },
        sensitiveInformationPolicyConfig={
            "piiEntitiesConfig": [
                {"type": "PHONE", "action": "ANONYMIZE"},
                {"type": "EMAIL", "action": "ANONYMIZE"},
                {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "ANONYMIZE"},
            ]
        },
        blockedInputMessaging="Request blocked by Sigma DataTech platform guardrail.",
        blockedOutputsMessaging="Response blocked by Sigma DataTech platform guardrail.",
    )
    guardrail_id = r["guardrailId"]
    log(f"  Created: {guardrail_id}")
    return guardrail_id


# ── Steps 3-8: Sub-agents ───────────────────────────────────────────────────────

def get_or_create_sub_agent(bedrock, name, dispatcher_arn, guardrail_id, account_id, role_arn):
    instructions = (AGENTS_DIR / INSTRUCTION_FILES[name]).read_text()
    tool_names   = AGENT_TOOLS[name]

    existing_id = find_agent_by_name(bedrock, name)
    if existing_id:
        log(f"  Already exists: {existing_id}")
        
        # 1. Update the agent configuration to ensure the role is correctly bound.
        bedrock.update_agent(
            agentId=existing_id,
            agentName=name,
            foundationModel=MODEL_ID,
            agentResourceRoleArn=role_arn,
            instruction=instructions,
            description=f"Sigma Intelligence Platform — {name}",
            idleSessionTTLInSeconds=1800,
            guardrailConfiguration={"guardrailIdentifier": guardrail_id, "guardrailVersion": "DRAFT"},
        )
        wait_for_agent_stable(bedrock, existing_id)
        
        # 2. Prepare only when Bedrock marks the draft as changed.
        prepare_agent_if_needed(bedrock, existing_id)
        
        # 3. Retrieve or create the alias 'v1' and point it at the latest version.
        alias_id, alias_arn = upsert_agent_alias(bedrock, existing_id, "v1")
        return existing_id, alias_id, alias_arn

    # Create agent
    r = bedrock.create_agent(
        agentName=name,
        foundationModel=MODEL_ID,
        instruction=instructions,
        description=f"Sigma Intelligence Platform — {name}",
        idleSessionTTLInSeconds=1800,
        guardrailConfiguration={"guardrailIdentifier": guardrail_id, "guardrailVersion": "DRAFT"},
        agentResourceRoleArn=role_arn,
    )
    agent_id = r["agent"]["agentId"]
    log(f"  Agent ID: {agent_id}")
    time.sleep(3)

    # Action group
    bedrock.create_agent_action_group(
        agentId=agent_id,
        agentVersion="DRAFT",
        actionGroupName="SigmaPlatformTools",
        actionGroupExecutor={"lambda": dispatcher_arn},
        functionSchema={"functions": build_functions(tool_names)},
        actionGroupState="ENABLED",
    )

    # Prepare
    bedrock.prepare_agent(agentId=agent_id)
    wait_for_agent(bedrock, agent_id, "PREPARED")
    log("  Prepared.")

    # Alias
    alias_id, alias_arn = upsert_agent_alias(bedrock, agent_id, "v1")

    return agent_id, alias_id, alias_arn


# ── Step 9: Supervisor ──────────────────────────────────────────────────────────

def get_or_create_supervisor(bedrock, sub_agent_data, dispatcher_arn, guardrail_id, account_id, role_arn):
    instructions = (AGENTS_DIR / INSTRUCTION_FILES["SupervisorAgent"]).read_text()

    supervisor_id = find_agent_by_name(bedrock, "SupervisorAgent")
    if not supervisor_id:
        r = bedrock.create_agent(
            agentName="SupervisorAgent",
            foundationModel=MODEL_ID,
            instruction=instructions,
            description="Sigma Intelligence Platform — Supervisor",
            idleSessionTTLInSeconds=1800,
            
            # ── ADD THIS LINE HERE ──
            agentCollaboration="SUPERVISOR", 
            # ────────────────────────
            
            guardrailConfiguration={"guardrailIdentifier": guardrail_id, "guardrailVersion": "DRAFT"},
            agentResourceRoleArn=role_arn,
        )
        supervisor_id = r["agent"]["agentId"]
        log(f"  Agent ID: {supervisor_id}")
        time.sleep(3)

        bedrock.create_agent_action_group(
            agentId=supervisor_id,
            agentVersion="DRAFT",
            actionGroupName="SigmaPlatformTools",
            actionGroupExecutor={"lambda": dispatcher_arn},
            functionSchema={"functions": build_functions(AGENT_TOOLS["SupervisorAgent"])},
            actionGroupState="ENABLED",
        )
    else:
        log(f"  Already exists: {supervisor_id}")
        bedrock.update_agent(
            agentId=supervisor_id,
            agentName="SupervisorAgent",
            foundationModel=MODEL_ID,
            instruction=instructions,
            description="Sigma Intelligence Platform — Supervisor",
            idleSessionTTLInSeconds=1800,
            agentCollaboration="SUPERVISOR",
            guardrailConfiguration={"guardrailIdentifier": guardrail_id, "guardrailVersion": "DRAFT"},
            agentResourceRoleArn=role_arn,
        )
        wait_for_agent_stable(bedrock, supervisor_id)

    # Associate sub-agents as collaborators
    log("  Associating sub-agents as collaborators...")
    for name, info in sub_agent_data.items():
        try:
            bedrock.associate_agent_collaborator(
                agentId=supervisor_id,
                agentVersion="DRAFT",
                agentDescriptor={"aliasArn": info["alias_arn"]},
                collaboratorName=name,
                collaborationInstruction=COLLAB_INSTRUCTIONS[name],
                relayConversationHistory="TO_COLLABORATOR",
            )
            log(f"    {name} ✓")
        except bedrock.exceptions.ConflictException:
            log(f"    {name} (already associated)")

    # Prepare supervisor (must re-prepare after adding new collaborators)
    log("  Preparing supervisor (includes all collaborators)...")
    wait_for_agent_stable(bedrock, supervisor_id)
    prepare_agent_if_needed(bedrock, supervisor_id)

    # Get or create alias, point to latest version.
    alias_id, _ = upsert_agent_alias(bedrock, supervisor_id, "v1")

    return supervisor_id, alias_id


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("SIGMA INTELLIGENCE PLATFORM — BEDROCK SETUP")
    log("Creates: Guardrail, 6 sub-agents, Supervisor agent")
    log("Takes:   5-8 minutes")
    log("Output:  IDs written to lab/.env automatically")
    log("=" * 60)

    env = load_env()
    role_arn = env.get("LAMBDA_ROLE_ARN", "").strip()
    if not role_arn:
        log("\n[ERROR] LAMBDA_ROLE_ARN not set in lab/.env")
        log("Fill it in and re-run this script.")
        sys.exit(1)

    sts        = boto3.client("sts", region_name=REGION)
    account_id = sts.get_caller_identity()["Account"]
    log(f"\nAccount : {account_id}")
    log(f"Region  : {REGION}")

    lc      = boto3.client("lambda",        region_name=REGION)
    iam     = boto3.client("iam",           region_name=REGION)
    # Change/Verify it looks like this:
    bedrock_main = boto3.client("bedrock", region_name="us-east-1")        # For Guardrails
    bedrock_agent = boto3.client("bedrock-agent", region_name="us-east-1") # For Agents

    # 1. Dispatcher Lambda
    dispatcher_arn = deploy_dispatcher(lc, role_arn, account_id)

    # 2. Guardrail
    guardrail_id = get_or_create_guardrail(bedrock_main)
    update_env({"GUARDRAIL_ID": guardrail_id})

    ensure_bedrock_agent_role_permissions(
        iam, role_arn, account_id, guardrail_id, dispatcher_arn
    )

    # 3-8. Sub-agents
    sub_agent_data = {}
    for i, name in enumerate(SUB_AGENTS, 3):
        log(f"\n[{i}/9] Creating {name}...")
        agent_id, alias_id, alias_arn = get_or_create_sub_agent(
            bedrock_agent, name, dispatcher_arn, guardrail_id, account_id, role_arn
        )
        sub_agent_data[name] = {
            "id": agent_id, "alias_id": alias_id, "alias_arn": alias_arn
        }

    # 9. Supervisor
    log(f"[9/9] Creating SupervisorAgent...")
    supervisor_id, supervisor_alias_id = get_or_create_supervisor(
        bedrock_agent, sub_agent_data, dispatcher_arn, guardrail_id, account_id, role_arn
    )

    # Write all IDs to .env
    update_env({
        "SUPERVISOR_AGENT_ID": supervisor_id,
        "SUPERVISOR_ALIAS_ID": supervisor_alias_id,
        "KNOWLEDGE_BASE_ID":   "LOCAL",
    })

    log("\n" + "=" * 60)
    log("SETUP COMPLETE — all IDs written to lab/.env")
    log("=" * 60)
    log(f"  Supervisor Agent ID : {supervisor_id}")
    log(f"  Supervisor Alias ID : {supervisor_alias_id}")
    log(f"  Guardrail ID        : {guardrail_id}")
    log(f"  Knowledge Base      : LOCAL (no AWS cost)")
    log("")
    log("Continue with Phase 2 manual investigation.")
    log("All agents ready for Phase 3 at 1:30 PM.")
    log("=" * 60)


if __name__ == "__main__":
    main()
