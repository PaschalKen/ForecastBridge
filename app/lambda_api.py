"""Entry point for running the FastAPI app on AWS Lambda.

Locally, uvicorn serves `app.main:app` over HTTP. On Lambda there's no server listening on a
port: each request arrives as an event (from the Function URL). Mangum converts that event into
a normal request for FastAPI, and FastAPI's response back into what Lambda expects.

Lambda handler setting: app.lambda_api.handler
"""
from mangum import Mangum

from app.main import app

# lifespan="off": the app has no startup/shutdown code, so skip those events
handler = Mangum(app, lifespan="off")
