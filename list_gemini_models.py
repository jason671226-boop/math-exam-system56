from google import genai
import streamlit as st

def main():
    api_key = str(st.secrets.get("GEMINI_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("GEMINI_KEY is empty in .streamlit/secrets.toml")

    client = genai.Client(api_key=api_key)

    print("Available Gemini models that support generateContent:")
    print("-" * 70)

    found = 0
    for model in client.models.list():
        name = getattr(model, "name", "")
        supported = getattr(model, "supported_actions", None)
        if supported is None:
            supported = getattr(model, "supported_generation_methods", None)

        supported_text = str(supported or "")
        if "generateContent" in supported_text or "generate_content" in supported_text:
            print(name)
            found += 1

    if found == 0:
        print("No generateContent-capable models were returned.")
        print("The account/key may not currently expose Gemini Developer API models.")

if __name__ == "__main__":
    main()
