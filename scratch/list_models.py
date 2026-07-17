import asyncio
import os
from google import genai
from dotenv import load_dotenv

# Load .env file
load_dotenv()

async def list_embedding_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not configured in .env.")
        return
        
    client = genai.Client(api_key=api_key)
    
    print("Fetching models list from Gemini API...")
    try:
        # List all models
        models = client.models.list()
        
        embedding_models = []
        for model in models:
            # Check if model supports embedding content
            methods = model.supported_actions or []
            if "embedContent" in methods or "embed_content" in str(methods).lower():
                embedding_models.append(model)
                
        print("\nSupported Embedding Models found:")
        for model in embedding_models:
            print(f"- Name: {model.name} (DisplayName: {model.display_name})")
            print(f"  Actions: {model.supported_actions}\n")
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(list_embedding_models())
