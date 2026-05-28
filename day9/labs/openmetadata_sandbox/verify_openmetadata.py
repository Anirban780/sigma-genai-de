import json
import urllib.request
import sys
import os

OPENMETADATA_HOST = os.getenv("OPENMETADATA_HOST", "http://localhost:8585")
URL_BASE = f"{OPENMETADATA_HOST.rstrip('/')}/api/v1"
JWT_TOKEN = os.getenv("OPENMETADATA_JWT_TOKEN") or os.getenv("OPENMETADATA_TOKEN")


class UnauthorizedError(Exception):
    """Raised when OpenMetadata requires an API token."""


def check_endpoint(endpoint):
    try:
        url = f"{URL_BASE}/{endpoint}"
        headers = {"Accept": "application/json"}
        if JWT_TOKEN:
            headers["Authorization"] = f"Bearer {JWT_TOKEN}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise UnauthorizedError(endpoint) from e
        else:
            print(f"❌ Error: OpenMetadata API request failed for /{endpoint}: HTTP {e.code}")
    except Exception as e:
        print(f"❌ Error: OpenMetadata API request failed for /{endpoint}: {e}")
        return None
    return None

def main():
    print("Checking OpenMetadata Sandbox installation status...")
    
    # 1. Check server status
    server_up = False
    try:
        urllib.request.urlopen(OPENMETADATA_HOST, timeout=5)
        server_up = True
    except Exception:
        pass
        
    if not server_up:
        print(f"❌ Error: OpenMetadata is not running on {OPENMETADATA_HOST}.")
        print("   Make sure you have started the local Docker sandbox:")
        print("   docker compose -f docker-compose.yml up -d")
        print("   Then wait for the server to finish initializing.")
        sys.exit(1)
        
    print("✓ OpenMetadata Server: RUNNING")

    if not JWT_TOKEN:
        print("❌ Error: OpenMetadata is running, but the verifier needs an API token.")
        print("   In OpenMetadata, generate a Personal Access Token from your profile, then run:")
        print('   export OPENMETADATA_JWT_TOKEN="paste-your-token-here"')
        print("   python verify_openmetadata.py")
        sys.exit(1)
    
    # 2. Check Database Services
    try:
        db_services = check_endpoint("services/databaseServices")
        db_service_count = len(db_services.get("data", [])) if db_services else 0
        print(f"✓ Database Services Configured: {db_service_count}")
        
        # 3. Check Ingested Tables
        tables_data = check_endpoint("tables")
        tables_count = len(tables_data.get("data", [])) if tables_data else 0
        print(f"✓ Tables Ingested: {tables_count}")
        
        # 4. Check Data Quality Test Cases
        test_cases_data = check_endpoint("dataQuality/testCases")
        test_cases_count = len(test_cases_data.get("data", [])) if test_cases_data else 0
        print(f"✓ Data Quality Test Cases Configured: {test_cases_count}")
    except UnauthorizedError as e:
        print(f"❌ Error: OpenMetadata API rejected /{e} with 401 Unauthorized.")
        print("   Your token is missing, expired, or invalid.")
        print("   Generate a new Personal Access Token and run:")
        print('   export OPENMETADATA_JWT_TOKEN="paste-your-token-here"')
        print("   python verify_openmetadata.py")
        sys.exit(1)

    checks_passed = (
        db_service_count >= 1
        and tables_count >= 1
        and test_cases_count >= 1
    )
    
    # Ensure target output directory exists
    output_dir = "../output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Write output to ../output/openmetadatalab.json
    result = {
        "status": "success" if checks_passed else "failed",
        "server_running": True,
        "database_services_count": db_service_count,
        "tables_ingested_count": tables_count,
        "data_quality_tests_count": test_cases_count,
        "openmetadata_verified": checks_passed
    }
    
    output_file = os.path.join(output_dir, "openmetadatalab.json")
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
        
    print(f"\nVerification file '{output_file}' generated.")
    print(json.dumps(result, indent=2))

    if not checks_passed:
        print("\n❌ Verification FAILED.")
        print("   Need at least 1 database service, 1 ingested table, and 1 data quality test case.")
        sys.exit(1)

    print("\n🎉 Verification SUCCESS!")

if __name__ == "__main__":
    main()
