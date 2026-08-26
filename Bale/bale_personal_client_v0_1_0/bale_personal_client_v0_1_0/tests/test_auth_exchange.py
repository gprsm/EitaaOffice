import httpx
import pytest

from bale_personal_client.auth import AuthClient
from bale_personal_client.config import BaleConfig
from bale_personal_client.grpc_web import GrpcWebClient


@pytest.mark.asyncio
async def test_exchange_jwt_reads_access_token_cookie():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer temporary.jwt"
        return httpx.Response(200, headers={"set-cookie": "access_token=final-token; Path=/; HttpOnly"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    grpc = GrpcWebClient(BaleConfig(), http)
    auth = AuthClient(BaleConfig(), grpc, http)
    assert await auth.exchange_jwt("temporary.jwt") == "final-token"
    await http.aclose()
