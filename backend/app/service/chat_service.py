import asyncio
import json
from collections.abc import AsyncIterator


async def stream_mock_chat() -> AsyncIterator[dict[str, str]]:
    for index in range(10):
        await asyncio.sleep(0.2)
        payload = {
            "index": index + 1,
            "message": f"mock message {index + 1}",
        }
        yield {
            "event": "message",
            "id": str(index + 1),
            "data": json.dumps(payload, ensure_ascii=False),
        }
