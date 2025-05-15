import langchain
from openai import OpenAI
import os
import gc
import logging
import time
import traceback
import psutil
import json
from dotenv import load_dotenv

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek/deepseek-prover-v2:free")

# Get max sizes from environment variables or use defaults
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", "3000"))
MAX_RESPONSE_SIZE = int(os.getenv("MAX_RESPONSE_SIZE", "50000"))

# Global OpenAI client
_openai_client = None

# Memory management helper function
def log_memory_usage():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / (1024 * 1024)
    logger.info(f"Current memory usage: {memory_mb:.2f} MB")
    return memory_mb

# Force garbage collection and report memory
def force_gc():
    before = log_memory_usage()
    gc.collect()
    after = log_memory_usage()
    logger.info(f"Garbage collection freed {before - after:.2f} MB")

def get_openai_client():
    """Get or create the OpenAI client"""
    global _openai_client
    if _openai_client is None:
        try:
            _openai_client = OpenAI(
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_API_BASE,
                timeout=120  # 2 minute timeout
            )
            logger.info("OpenAI client created successfully")
        except Exception as e:
            logger.error(f"Error creating OpenAI client: {str(e)}")
            raise
    return _openai_client

def generate_manim_code(prompt):
    """Generate Manim code using direct OpenAI API calls to avoid LangChain memory issues"""
    start_time = time.time()
    log_memory_usage()
    
    try:
        # Trim prompt if it's too long
        if len(prompt) > MAX_REQUEST_SIZE:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to {MAX_REQUEST_SIZE} chars")
            prompt = prompt[:MAX_REQUEST_SIZE]
            
        logger.info(f"Generating Manim code for prompt of length {len(prompt)}")
        
        # Simplified system prompt to reduce memory usage
        system_prompt = """
Generate complete, production-ready Manim code for creating educational animations. Provide clean, functional code without placeholders, TODOs, or partial implementations. Include all imports, ensure full implementation, use proper animation timing, and include helpful comments. Output ONLY the Python code, ready to execute with Manim."""

        # Get the OpenAI client
        client = get_openai_client()
        
        logger.info("Sending request to OpenAI API")
        
        # Make the request with streaming to reduce memory usage
        try:
            # Using streaming to reduce memory usage
            accumulated_response = ""
            
            # Create the API request
            response_stream = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                max_tokens=4000,
                temperature=0.2
            )
            
            # Process the streaming response
            for chunk in response_stream:
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    accumulated_response += content
                    
                    # Limit size if it gets too large
                    if len(accumulated_response) > MAX_RESPONSE_SIZE:
                        logger.warning(f"Response too large ({len(accumulated_response)} chars), truncating")
                        accumulated_response = accumulated_response[:MAX_RESPONSE_SIZE] + "\n\n# Note: Response was truncated due to size limits"
                        break
            
            result = accumulated_response
            
        except Exception as api_error:
            logger.error(f"Error during OpenAI API call: {str(api_error)}")
            logger.error(traceback.format_exc())
            result = f"# Error during code generation: {str(api_error)}\n# Please try again with a simpler prompt."
        
        # Optionally, strip markdown code block markers
        if result.startswith("```python"):
            result = result[len("```python"):].strip()
        if result.endswith("```"):
            result = result[:-3].strip()
            
        # Check if the result is empty or too short
        if len(result) < 50:
            logger.warning(f"Generated code is suspiciously short ({len(result)} chars)")
            if len(result) < 10:
                result = "# Error: Generated code was too short or empty. Please try again with a simpler prompt."
        
        # Force garbage collection
        force_gc()
        
        process_time = time.time() - start_time
        logger.info(f"Successfully generated code of length {len(result)} in {process_time:.2f} seconds")
        return result

    except Exception as e:
        logger.error(f"Error generating code: {str(e)}")
        logger.error(traceback.format_exc())
        force_gc()
        return f"// Error generating code: {str(e)}"

def improve_prompt(prompt):
    """Improve a prompt using direct OpenAI API calls to avoid LangChain memory issues"""
    logger.info("improve_prompt function called")
    log_memory_usage()
    
    try: 
        # Trim prompt if it's too long
        if len(prompt) > MAX_REQUEST_SIZE:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to {MAX_REQUEST_SIZE} chars")
            prompt = prompt[:MAX_REQUEST_SIZE]
        
        # Simplified system prompt to reduce memory usage
        system_prompt = """
Transform vague animation prompts into detailed specifications that can be fully implemented. Include specific visual elements, animations, timing, technical details (objects, methods, coordinates), and specify the sequence of animation steps. Eliminate all ambiguity. DO NOT generate code - provide a comprehensive blueprint using proper Manim terminology."""
        
        # Get the OpenAI client
        client = get_openai_client()
        
        logger.info("Sending request to OpenAI API for prompt improvement")
        
        # Make the request with streaming to reduce memory usage
        try:
            # Using streaming to reduce memory usage
            accumulated_response = ""
            
            # Create the API request
            response_stream = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Prompt: {prompt}"}
                ],
                stream=True,
                max_tokens=2000,
                temperature=0.3
            )
            
            # Process the streaming response
            for chunk in response_stream:
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    accumulated_response += content
                    
                    # Limit size if it gets too large
                    if len(accumulated_response) > MAX_REQUEST_SIZE * 2:
                        logger.warning(f"Improved prompt too large ({len(accumulated_response)} chars), truncating")
                        accumulated_response = accumulated_response[:MAX_REQUEST_SIZE * 2] + "\n\nNote: Response was truncated due to size limits."
                        break
            
            improved = accumulated_response
            
        except Exception as api_error:
            logger.error(f"Error during OpenAI API call for prompt improvement: {str(api_error)}")
            logger.error(traceback.format_exc())
            improved = f"Error improving prompt: {str(api_error)}. Please try again with a simpler description."
        
        # Check if result is too short
        if len(improved) < 50:
            logger.warning(f"Improved prompt is suspiciously short ({len(improved)} chars)")
            if len(improved) < 10:
                improved = "Error: Could not improve the prompt. Please try with a different description."
        
        # Force garbage collection
        force_gc()
        
        logger.info(f"Successfully improved prompt from {len(prompt)} to {len(improved)} chars")
        return improved.strip()
        
    except Exception as e:
        logger.error(f"Error in improve_prompt: {str(e)}")
        logger.error(traceback.format_exc())
        force_gc()
        raise Exception(f"Failed to improve prompt: {str(e)}")