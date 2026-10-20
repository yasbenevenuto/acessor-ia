import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from dotenv import load_dotenv
load_dotenv()

# ==============================================================================
# MODELOS
# ==============================================================================
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    top_p=0.95,
    api_key=os.getenv("GEMINI_API_KEY"),
)

llm_groq_pesado = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.7,
    api_key=os.getenv("GROQ_API_KEY"),
    reasoning_format="parsed",  # separa o raciocínio em additional_kwargs['reasoning_content']
)

llm_rapido = ChatGroq(
    model="qwen/qwen3.8-27b",
    temperature=0.0,
    api_key=os.getenv("GROQ_API_KEY"),
    reasoning_format="parsed",
    reasoning_effort="none",  
    max_tokens=1000,         
)

# Gemini com fallback para Groq pesado
llm_especialista = llm_gemini.with_fallbacks([llm_groq_pesado])