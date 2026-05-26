from typing import Dict, List, Tuple
from pyspark.sql import DataFrame
from pyspark.sql.types import StructType, StructField, StringType, FloatType, IntegerType

def detect_schema_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str]) -> Dict[str, any]:
    new_columns = {k: v for k, v in actual_schema.items() if k not in expected_schema}
    removed_columns = {k: v for k, v in expected_schema.items() if k not in actual_schema}
    type_changes = {k: (expected_schema[k], actual_schema[k]) for k in expected_schema if expected_schema[k]!= actual_schema[k]}
    drift_severity = 'NONE'
    
    if new_columns:
        if any("null" not in v for v in new_columns.values()):
            drift_severity = 'HIGH'
        else:
            drift_severity = 'LOW'
    
    if removed_columns:
        drift_severity = 'BREAKING'
    
    return {
        "new_columns": new_columns,
        "removed_columns": removed_columns,
        "type_changes": type_changes,
        "drift_severity": drift_severity
    }

def decide_action(drift_report: Dict[str, any]) -> Dict[str, Dict[str, str]]:
    decisions = {}
    
    for column, dtype in drift_report["new_columns"].items():
        if dtype.endswith(" nullable"):
            if column == "discount_amount":
                decisions[column] = {"action": "FLAG_ANOMALY", "reason": "Potential revenue impact", "risk_level": "HIGH"}
            else:
                decisions[column] = {"action": "ADD_TO_SCHEMA", "reason": "Safe to add", "risk_level": "LOW"}
    
    for column, (old_type, new_type) in drift_report["type_changes"].items():
        if "->" in new_type:
            orig, new = new_type.split("->")
            if orig == "int" and new == "float":
                decisions[column] = {"action": "ADD_TO_SCHEMA", "reason": "Type widening", "risk_level": "LOW"}
            elif orig == "float" and new == "int":
                decisions[column] = {"action": "FLAG_ANOMALY", "reason": "Type narrowing", "risk_level": "HIGH"}
    
    for column in drift_report["removed_columns"]:
        decisions[column] = {"action": "HALT", "reason": "Cannot drop column silently", "risk_level": "BREAKING"}
    
    return decisions

def apply_schema_evolution(spark_df: DataFrame, decisions: Dict[str, Dict[str, str]], updated_schema: Dict[str, str]) -> Tuple[DataFrame, List[str]]:
    migration_notes = []
    for column, decision in decisions.items():
        if decision["action"] == "DROP_SILENTLY":
            spark_df = spark_df.drop(column)
        elif decision["action"] == "ADD_TO_SCHEMA":
            migration_notes.append(f"Added column: {column}")
        elif decision["action"] == "FLAG_ANOMALY":
            spark_df = spark_df.withColumn(f"{column}_anomaly_flag", spark_df[column].isNull().cast("boolean"))
            migration_notes.append(f"Flagged anomaly for column: {column}")
    
    return spark_df, migration_notes

def handle_drift(expected_schema: Dict[str, str], actual_schema: Dict[str, str], spark_df: DataFrame = None) -> Dict[str, any]:
    drift_report = detect_schema_drift(expected_schema, actual_schema)
    decisions = decide_action(drift_report)
    
    if spark_df is not None:
        evolved_df, migration_notes = apply_schema_evolution(spark_df, decisions, actual_schema)
        print("Drift Report:")
        print(f"New Columns: {drift_report['new_columns']}")
        print(f"Removed Columns: {drift_report['removed_columns']}")
        print(f"Type Changes: {drift_report['type_changes']}")
        print(f"Drift Severity: {drift_report['drift_severity']}")
        print("Migration Notes:")
        for note in migration_notes:
            print(note)
        return {"drift_report": drift_report, "decisions": decisions, "migration_notes": migration_notes, "evolved_df": evolved_df}
    else:
        print("Drift Report:")
        print(f"New Columns: {drift_report['new_columns']}")
        print(f"Removed Columns: {drift_report['removed_columns']}")
        print(f"Type Changes: {drift_report['type_changes']}")
        print(f"Drift Severity: {drift_report['drift_severity']}")
        print("Decisions:")
        for column, decision in decisions.items():
            print(f"{column}: {decision['action']} ({decision['reason']})")
        return {"drift_report": drift_report, "decisions": decisions}
