# main.py
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()  # .env 파일 내용 환경변수로 로드



# 🔑 OpenAI 키
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# MCP 서버 스크립트 경로 (같은 폴더에 mcp_server.py 있다고 가정)
MCP_SCRIPT = Path(__file__).with_name("mcp_server.py")


SYSTEM_PROMPT = """
너는 쇼핑몰 고객센터 상담원이다.
지원 가능한 기능:
- 배송 조회: 주문번호를 이용해서 현재 배송 상태를 알려줄 수 있다.

규칙:
1. 사용자가 '배송', '택배', '배송조회' 같은 말을 하면, 반드시 'track_delivery' 도구를 활용하려고 시도해라.
2. 주문번호를 모르면 먼저 사용자에게 주문번호를 물어봐라.
3. 도구 호출 결과를 받으면, 한국어로 친절하게 요약해서 알려줘라.
"""


# LLM에게 노출할 "tool" 스펙 (이 tool을 실제로는 MCP로 라우팅할 것)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "track_delivery",
            "description": "주문번호(order_id)로 배송 상태를 조회한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "주문번호, 예: 'ORDER123'",
                    }
                },
                "required": ["order_id"],
            },
        },
    }
]


async def call_mcp_tool(tool_name: str, arguments: dict):
    """
    MCP 서버(mcp_server.py)에 stdio로 붙어서 해당 tool을 실행하고 결과를 반환.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SCRIPT)],
        env={**os.environ},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return result


def call_llm_with_tools(messages):
    """
    OpenAI LLM에 messages + tools를 보내서
    - 도구 호출이 필요한지 판단하게 하고
    - tool_call 결과를 그대로 리턴.
    """
    resp = client.chat.completions.create(
        model="gpt-5-mini-2025-08-07",  # 또는 네가 쓰는 모델명
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    return resp

def extract_mcp_tool_output(mcp_result) -> str:
    """
    MCP CallToolResult에서 LLM에 줄 문자열만 뽑아내는 헬퍼.
    """
    # 1) structuredContent가 있으면 그걸 JSON으로
    if getattr(mcp_result, "structuredContent", None):
        try:
            return json.dumps(mcp_result.structuredContent, ensure_ascii=False)
        except Exception:
            pass

    # 2) content[0].text 형식이면 그 텍스트 사용
    content = getattr(mcp_result, "content", None)
    if content:
        first = content[0]
        if hasattr(first, "text") and first.text is not None:
            return first.text
        # 혹시 dict 같은게 들어있으면
        try:
            return json.dumps(first, ensure_ascii=False)
        except TypeError:
            return str(first)

    # 3) 최후의 수단: 그냥 문자열 변환
    return str(mcp_result)


async def chat_once(user_input: str):
    # 1) 유저 메시지까지 넣고 1차 LLM 호출
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    first = call_llm_with_tools(messages)
    msg = first.choices[0].message

    # 2) LLM이 tool_calls를 요청했는지 체크
    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments or "{}")

        print(f"\n🛠 LLM이 툴 호출 요청: {tool_name}({tool_args})")

        # 3) MCP 서버에 실제 툴 호출
        mcp_result = await call_mcp_tool(tool_name, tool_args)
        print(f"📦 MCP 툴 결과(raw): {mcp_result}")

        # 4) 툴 결과를 LLM에 다시 던져서 최종 답변 생성
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call],
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": json.dumps(mcp_result),
            }
        )

        final = client.chat.completions.create(
            model="gpt-5.1-mini",
            messages=messages,
        )
        answer = final.choices[0].message.content
        print(f"\n💬 최종 답변:\n{answer}\n")

    else:
        # 도구 필요 없이 바로 답한 경우
        print(f"\n💬 LLM 직접 답변:\n{msg.content}\n")


async def main():
    # 한 번 테스트: 주문번호까지 다 말해주는 케이스
    print("=== 테스트 1: 'ORDER123 배송 조회해줘' ===")
    await chat_once("ORDER123 배송 조회해줘")

    # 한 번 테스트: 주문번호 없이 “배송조회가 궁금해요”
    print("\n=== 테스트 2: '나 배송조회가 궁금해요' ===")
    await chat_once("나 배송조회가 궁금해요")


if __name__ == "__main__":
    asyncio.run(main())
