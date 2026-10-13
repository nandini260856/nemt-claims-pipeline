"""Project settings in one place, so every step reads the same paths and dates."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # landing zone (S3 "raw/" bucket in AWS)
OUTBOUND_DIR = DATA_DIR / "outbound"  # 837P claim files we send to payers
INBOUND_DIR = DATA_DIR / "inbound"    # 835 remittance files payers send back
WAREHOUSE = DATA_DIR / "warehouse.duckdb"  # local stand-in for Redshift
SQL_DIR = ROOT / "sql"
REPORT_DIR = ROOT / "reports"

# The day the billing run happens. Timely filing is measured against this.
RUN_DATE = date(2026, 10, 1)
SERVICE_START = date(2026, 1, 1)
SERVICE_END = date(2026, 9, 30)

SEED = 42
N_MEMBERS = 2500
N_TRIPS = 30000
