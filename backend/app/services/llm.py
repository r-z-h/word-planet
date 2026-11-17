"""Phase B · Step 3：调用外部 LLM（DeepSeek，OpenAI 兼容 /chat/completions）。

- 只把「检索到的片段 + 用户问题」交给模型，组织成一句中文回答；
- 复用全局 httpx 连接（省 TLS 握手）；超时较短 + max_tokens 有限，避免长思考卡死；
- 任何失败/超时都抛异常，由上层降级为「返回原文片段」。
"""

from __future__ import annotations

import httpx

from ..config import settings

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=httpx.Timeout(settings.llm_timeout, connect=5.0))
    return _client


def is_configured() -> bool:
    return bool(settings.llm_api_key and settings.llm_model and settings.llm_base_url)


def _post(payload: dict) -> str:
    if settings.llm_reasoning_effort:
        payload.setdefault("reasoning_effort", settings.llm_reasoning_effort)
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    resp = _get_client().post(
        url,
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json=payload,
    )
    resp.raise_for_status()
    data = resp.json()
    return str(data["choices"][0]["message"]["content"]).strip()


def generate(question: str, contexts: list[dict], *, timeout: float | None = None) -> str:
    """contexts: [{'question','answer','source_title'}, ...] → 生成回答文本。"""
    if not is_configured():
        raise RuntimeError("LLM 未配置（缺少 LLM_API_KEY / LLM_MODEL）")
    material = "\n\n".join(
        f"[资料{i + 1}] {c.get('source_title', '')}\n问：{c['question']}\n答：{c['answer']}"
        for i, c in enumerate(contexts)
    )
    system = (
        "你是 Word Planet 学习平台的站内助手。规则："
        "1) 只能依据【资料】回答；资料里没有的，直接回答“这个我暂时答不上来，可以到对应页面看看”。"
        "2) 用中文、简短、亲切的少儿口吻，一两句话即可。"
        "3) 不要编造数字、词义或资料以外的内容。"
    )
    user = f"【资料】\n{material}\n\n【问题】\n{question}\n\n请依据资料用一两句话回答。"
    return _post(
        {
            "model": settings.llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": settings.llm_max_tokens,
            "stream": False,
        }
    )


def chat(messages: list[dict], *, timeout: float | None = None) -> str:
    """通用 OpenAI 兼容 chat：直接传 messages（供 RAG 引擎组织多片段回答用）。"""
    if not is_configured():
        raise RuntimeError("LLM 未配置（缺少 LLM_API_KEY / LLM_MODEL）")
    return _post(
        {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": settings.llm_max_tokens,
            "stream": False,
        }
    )
