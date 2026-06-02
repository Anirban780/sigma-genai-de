import os, sys
# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lab.trigger.pipeline_trigger import validate_env, health_check

def main():
    """Simple validation script for Day12 project.
    It checks that required environment variables are set and that all Lambda
    tools are present (health_check). If any check fails, the script exits with
    a non‑zero status code so that CI pipelines can catch the failure.
    """
    # Validate required .env variables
    validate_env()

    # Run the health check – this prints a report and returns a boolean
    if not health_check():
        raise SystemExit("[ERROR] Health check failed – some Lambda tools are missing.")
    print("[INFO] validate_day12 PASSED")

if __name__ == "__main__":
    main()
