import config

_DEFAULTS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
}


def get_llm(structured_output_model=None):
    """Return configured LLM.

    Backend and model are controlled by env vars:
        LLM_BACKEND  — "anthropic" (default) | "gemini" | "openai"
        LLM_MODEL    — any model name for that backend; falls back to
                       provider default if unset

    Pass a Pydantic model class to get structured output.
    """
    backend = config.LLM_BACKEND
    model = config.LLM_MODEL or _DEFAULTS.get(backend, "")

    if not model:
        raise ValueError(f"Unknown LLM_BACKEND '{backend}'. Set LLM_BACKEND and optionally LLM_MODEL.")

    if backend == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0,
        )
    elif backend == "openai":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model,
            api_key=config.OPENAI_API_KEY,
            temperature=0,
        )
    else:  # anthropic (default)
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model=model,
            api_key=config.ANTHROPIC_API_KEY,
            temperature=0,
        )

    if structured_output_model is not None:
        return llm.with_structured_output(structured_output_model)
    return llm
