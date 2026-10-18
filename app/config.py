import os

from dotenv import load_dotenv

# Read settings from a .env file in the project root, if one exists.
# Real environment variables (e.g. set by AWS Lambda later) take priority.
load_dotenv()

OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")

# No default: the bucket name is specific to your AWS account
S3_BUCKET = os.getenv("S3_BUCKET")
