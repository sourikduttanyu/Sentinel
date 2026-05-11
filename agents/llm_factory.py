import config


def get_llm(structured_output_model=None):
    """Return configured LLM. Pass a Pydantic model to get structured output."""
    if config.LLM_BACKEND == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0,
        )
    else:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=config.ANTHROPIC_API_KEY,
            temperature=0,
        )

    if structured_output_model is not None:
        return llm.with_structured_output(structured_output_model)
    return llm
