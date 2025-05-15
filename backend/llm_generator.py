import langchain
from openai import OpenAI
from langchain_openai import ChatOpenAI  # Updated import
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
import os
import gc
import logging
from dotenv import load_dotenv
import time

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek/deepseek-prover-v2:free")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "deepseek/deepseek-prover-v2:free")  # Fallback model
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "180"))

# Global LLM instance
_llm_instance = None
_using_fallback = False

def get_llm(use_fallback=False):
    """Lazy-load the LLM instance only when needed"""
    global _llm_instance, _using_fallback
    
    # Reset the instance if we're switching between primary and fallback
    if use_fallback and not _using_fallback:
        _llm_instance = None
        _using_fallback = True
    elif not use_fallback and _using_fallback:
        _llm_instance = None
        _using_fallback = False
    
    if _llm_instance is None:
        try:
            # Choose which model to use
            model = FALLBACK_MODEL if use_fallback else DEFAULT_MODEL
            
            logger.info(f"Creating LLM instance with model: {model}")
            logger.info(f"API Base: {OPENROUTER_API_BASE}")
            
            # Add HTTP headers required by OpenRouter
            headers = {
                "HTTP-Referer": "https://automanim.app",  # Replace with your actual domain
                "X-Title": "AutoManim"
            }
            
            _llm_instance = ChatOpenAI(
                openai_api_key=OPENROUTER_API_KEY,
                openai_api_base=OPENROUTER_API_BASE,
                model_name=model,
                request_timeout=REQUEST_TIMEOUT,
                max_retries=2,
                default_headers=headers
            )
            logger.info(f"LLM instance created successfully using {'fallback' if use_fallback else 'primary'} model")
        except Exception as e:
            logger.error(f"Error creating LLM instance: {str(e)}")
            raise
    return _llm_instance

def generate_manim_code(prompt):
    try:
        # Trim prompt if it's too long
        if len(prompt) > 5000:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to 5000 chars")
            prompt = prompt[:5000]
            
        logger.info(f"Generating Manim code for prompt of length {len(prompt)}")
        
        system_template = """
You are an expert programmer specializing in creating Manim animations for educational content. Your task is to write clean, executable Manim code that implements the user's request completely.

Key requirements:
1. Import necessary modules (manim, numpy, etc.)
2. Create a Scene class with a descriptive name
3. Implement a full construct method with all requested features
4. Include helper methods as needed for organization
5. Implement complete, functioning code without TODOs or placeholders
6. Add appropriate wait times between animation steps
7. Include the render code with if __name__ == "__main__"

Your response must ONLY contain the Python code, with no additional explanations outside code comments.

Example structure:
```python
from manim import *
import numpy as np

class YourAnimation(Scene):
    def construct(self):
        # Complete implementation here
        title = Text("Animation Title")
        self.play(Write(title))
        self.wait(1)
        
        # Rest of the implementation
        # ...

if __name__ == "__main__":
    scene = YourAnimation()
    scene.render()
```"""
        systemMessage = SystemMessagePromptTemplate.from_template(system_template)
        human_template = "Question : {question}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)
        chat_prompt = ChatPromptTemplate.from_messages([systemMessage, human_message])
        
        # Try with primary model first, then fallback if needed
        use_fallback = False
        retry_delay = 2  # seconds
        total_attempts = 0
        
        for model_attempt in range(2):  # Try primary, then fallback if needed
            if total_attempts >= MAX_RETRIES:
                break
                
            # Try to get the LLM instance
            try:
                llm = get_llm(use_fallback=use_fallback)
            except Exception as e:
                logger.error(f"Failed to initialize {'fallback' if use_fallback else 'primary'} LLM: {str(e)}")
                if not use_fallback:
                    # Try fallback model
                    use_fallback = True
                    continue
                else:
                    # Both models failed to initialize
                    return f"// Error: Failed to initialize AI models: {str(e)}"

            # Create a new chain for each request to avoid memory leaks
            llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
            
            # Add retry logic for API calls
            for attempt in range(MAX_RETRIES - total_attempts):
                total_attempts += 1
                try:
                    model_type = "fallback" if use_fallback else "primary"
                    logger.info(f"Attempt {total_attempts}/{MAX_RETRIES} using {model_type} model")
                    
                    response = llm_chain.invoke({"question": prompt})
                    
                    # Extract the text from the response object and clear references
                    if isinstance(response, dict) and "text" in response:
                        result = response["text"]
                        # Clear references
                        response.clear()
                    else:
                        result = str(response)
                    
                    # Successfully got a response, break the retry loop
                    logger.info(f"Successfully generated code using {model_type} model")
                    
                    # Optionally, strip markdown code block markers
                    if result.startswith("```python"):
                        result = result[len("```python"):].strip()
                    if result.endswith("```"):
                        result = result[:-3].strip()
                        
                    # Force garbage collection to free memory
                    chat_prompt = None
                    llm_chain = None
                    gc.collect()
                    
                    logger.info(f"Successfully generated code of length {len(result)}")
                    return result
                    
                except Exception as e:
                    logger.error(f"Attempt {total_attempts} with {model_type} model failed: {str(e)}")
                    if total_attempts < MAX_RETRIES:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        gc.collect()  # Force garbage collection between retries
                    
                    # If using primary model and hit an error, try fallback
                    if not use_fallback and total_attempts >= (MAX_RETRIES // 2):
                        logger.info("Switching to fallback model")
                        use_fallback = True
                        break
            
        # If we get here, all attempts failed
        logger.error("All generation attempts failed")
        return "// Error: Unable to generate code after multiple attempts. Please try again with a simpler prompt."

    except Exception as e:
        logger.error(f"Error generating code: {str(e)}", exc_info=True)
        gc.collect()  # Try to free memory even on failure
        return f"// Error generating code: {str(e)}\n// Please try again with a simpler prompt or contact support if the issue persists."

def improve_prompt(prompt):
    logger.info("improve_prompt function called")
    try: 
        # Trim prompt if it's too long
        if len(prompt) > 5000:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to 5000 chars")
            prompt = prompt[:5000]
            
        system_template = """
Your task is to expand a user's vague animation request into detailed instructions for creating a Manim animation.

Provide specific details on:
1. Visual elements to include (shapes, equations, text)
2. Animation sequences and transitions
3. Colors, positions, and styling
4. Timing and flow of the animation
5. Mathematical formulas and notations (if applicable)

Do NOT generate code. Instead, provide a detailed description that would allow a programmer to implement the animation without guesswork.

Format your response as a clear, detailed specification, focusing on Manim's specific objects and methods."""
        system_message = SystemMessagePromptTemplate.from_template(system_template)

        human_template = "Prompt: {prompt}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)

        chat_prompt = ChatPromptTemplate.from_messages([system_message, human_message])
        
        # Try with primary model first, then fallback if needed
        use_fallback = False
        retry_delay = 2  # seconds
        total_attempts = 0
        
        for model_attempt in range(2):  # Try primary, then fallback if needed
            if total_attempts >= MAX_RETRIES:
                break
                
            # Try to get the LLM instance
            try:
                llm = get_llm(use_fallback=use_fallback)
            except Exception as e:
                logger.error(f"Failed to initialize {'fallback' if use_fallback else 'primary'} LLM: {str(e)}")
                if not use_fallback:
                    # Try fallback model
                    use_fallback = True
                    continue
                else:
                    # Both models failed to initialize
                    raise Exception(f"Failed to initialize AI models: {str(e)}")

            # Create a new chain for each request
            llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
            
            # Add retry logic for API calls
            for attempt in range(MAX_RETRIES - total_attempts):
                total_attempts += 1
                try:
                    model_type = "fallback" if use_fallback else "primary"
                    logger.info(f"Attempt {total_attempts}/{MAX_RETRIES} using {model_type} model to improve prompt")
                    
                    response = llm_chain.invoke({"prompt": prompt})
                    
                    # Extract the text from the response object
                    if isinstance(response, dict) and "text" in response:
                        improved = response["text"]
                        # Clear references
                        response.clear()
                    else:
                        improved = str(response)
                    
                    # Successfully got a response
                    logger.info(f"Successfully improved prompt using {model_type} model")
                    
                    # Clear references to help with garbage collection
                    chat_prompt = None
                    llm_chain = None
                    gc.collect()
                    
                    logger.info(f"Successfully improved prompt of length {len(improved)}")
                    return improved.strip()
                    
                except Exception as e:
                    logger.error(f"Attempt {total_attempts} with {model_type} model failed: {str(e)}")
                    if total_attempts < MAX_RETRIES:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        gc.collect()  # Force garbage collection between retries
                    
                    # If using primary model and hit an error, try fallback
                    if not use_fallback and total_attempts >= (MAX_RETRIES // 2):
                        logger.info("Switching to fallback model for prompt improvement")
                        use_fallback = True
                        break
            
        # If we get here, all attempts failed
        logger.error("All prompt improvement attempts failed")
        raise Exception("Unable to improve prompt after multiple attempts. Please try again with a clearer prompt.")
        
    except Exception as e:
        logger.error(f"Error in improve_prompt: {str(e)}", exc_info=True)
        gc.collect()  # Try to free memory even on failure
        raise Exception(f"Failed to improve prompt: {str(e)}")