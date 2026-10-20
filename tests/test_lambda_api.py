import json

from app.lambda_api import handler


def function_url_event(path: str, query: str = "") -> dict:
    """A minimal copy of the event a Lambda Function URL sends for a GET request."""
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": query,
        "headers": {"host": "example.lambda-url.eu-north-1.on.aws", "accept": "*/*"},
        "requestContext": {
            "http": {"method": "GET", "path": path, "protocol": "HTTP/1.1", "sourceIp": "127.0.0.1", "userAgent": "test"},
            "domainName": "example.lambda-url.eu-north-1.on.aws",
            "stage": "$default",
        },
        "isBase64Encoded": False,
    }


def test_health_through_lambda():
    response = handler(function_url_event("/health"), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "ok"}


def test_home_page_through_lambda():
    response = handler(function_url_event("/"), None)

    assert response["statusCode"] == 200
    assert "ForecastBridge" in response["body"]


def test_unknown_location_through_lambda():
    response = handler(function_url_event("/forecast", "location=paris"), None)

    assert response["statusCode"] == 404
