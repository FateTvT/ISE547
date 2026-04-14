import asyncio
import json
from collections.abc import AsyncIterator

MOCK_RESPONSE_CHUNKS = [
    "根据",
    "您提供的",
    "症状描述",
    "（偏头痛、",
    "恶心、",
    "畏光），",
    "系统经过",
    "医学知识库",
    "比对，",
    "为您生成以下",
    "初步分析报告：\n\n",
    "### 1. 可能的诊断结果\n",
    "* **血管性偏头痛** (85% 相关性)\n",
    "* **紧张性头痛** (10% 相关性)\n",
    "* **丛集性头痛** (5% 相关性)\n\n",
    "### 2. 建议采取的措施\n",
    "* **环境调节**：请立即移步至安静、",
    "避光的房间休息。\n",
    "* **体温监测**：记录当前的体温是否伴随发热。\n",
    "* **补充水分**：建议饮用少量的温开水。\n\n",
    "### 3. 需警惕的症状 (Red Flags)\n",
    "如果出现以下情况，请立刻拨打急救电话或前往急诊：\n",
    "* 伴随剧烈的呕吐或言语不清；\n",
    "* 视力突然模糊且无法恢复；\n",
    "* 肢体出现麻木感。\n\n",
    "--- \n",
    "> **免责声明**：本结果基于算法逻辑生成，仅供参考，不作为临床诊断依据。请及时咨询专业医师。",
]


async def stream_mock_chat() -> AsyncIterator[dict[str, str]]:
    for index, message in enumerate(MOCK_RESPONSE_CHUNKS, start=1):
        await asyncio.sleep(0.2)
        payload = {
            "index": index,
            "message": message,
        }
        yield {
            "event": "message",
            "id": str(index),
            "data": json.dumps(payload, ensure_ascii=False),
        }
