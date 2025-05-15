import langchain
from openai import OpenAI
import os
import gc
import logging
import time
import traceback
import psutil
import json
import re
from dotenv import load_dotenv

# Setup logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "microsoft/phi-4-reasoning-plus:free")

# Get max sizes from environment variables or use defaults
MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", "10000"))
MAX_RESPONSE_SIZE = int(os.getenv("MAX_RESPONSE_SIZE", "100000"))

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
                timeout=150  # 2.5 minute timeout
            )
            logger.info("OpenAI client created successfully")
        except Exception as e:
            logger.error(f"Error creating OpenAI client: {str(e)}")
            raise
    return _openai_client

def clean_thinking_output(text):
    """Remove thinking process and intermediate steps from the output"""
    # Remove any lines containing "thinking" markers
    clean_text = re.sub(r'(?i)# ?thinking:?.*?(\n|$)', '', text)
    
    # Remove any lines with intermediate reasoning
    clean_text = re.sub(r'(?i)# ?reasoning:?.*?(\n|$)', '', clean_text)
    clean_text = re.sub(r'(?i)# ?step:?.*?(\n|$)', '', clean_text)
    
    # If there are markdown code blocks, extract only the code
    if "```python" in clean_text:
        code_blocks = re.findall(r'```python(.*?)```', clean_text, re.DOTALL)
        if code_blocks:
            clean_text = code_blocks[0].strip()
    
    # Remove explanatory text at beginning and end
    clean_text = re.sub(r'^.*?(?=from manim import|import manim)', '', clean_text, flags=re.DOTALL)
    clean_text = re.sub(r'(?<=if __name__ == "__main__".*render\(\)).*$', '', clean_text, flags=re.DOTALL)
    
    return clean_text.strip()

def generate_manim_code(prompt):
    """Generate Manim code using direct OpenAI API calls to avoid LangChain memory issues"""
    start_time = time.time()
    log_memory_usage()
    
    try:
        logger.info(f"Generating Manim code for prompt of length {len(prompt)}")
        
        # Simplified system prompt to reduce memory usage
        system_prompt = """
You are an AI specialized in generating Manim code specifically designed to create educational animations, similar to those seen in 3Blue1Brown's videos. Your primary objective is to provide clean, functional, and fully executable Manim code without any additional text or explanations. 

### Instructions:
1. **Imports**: Start by importing all necessary modules from the Manim library (`from manim import *`). If any special plugins are required, explicitly mention them in comments, but avoid using them unless prompted.

2. **Code Structure**:
   - All your output code must be contained within a class that inherits from `Scene` and defines the `construct` method.
   - Ensure the code is wrapped in `if __name__ == "__main__":` with the `render` call to render the scene.
   - Use `self.play()` to include animations.
   - Use meaningful variable names and consistent indentation (4 spaces per level).
   - Include comments only to explain complex or non-obvious parts of the code, but avoid over-commenting.

3. **Best Practices**:
   - Make use of the latest version of Manim (Manim Community `v0.18.0` or higher).
   - Use LaTeX for mathematical symbols and expressions (`MathTex`, `Tex`).
   - Prefer smooth transitions (`Transform`, `ReplacementTransform`).
   - Use built-in animation functions (`Create`, `Write`, `FadeOut`, etc.) and path animations (`MoveAlongPath`).
   - Avoid overriding defaults unless necessary (keep code minimal).

4. **Output Format**:
   - Provide **only** the complete Python code, ready to be executed with `manim`.
   - Do **not** include any additional text such as explanations, triple backticks, or annotations beyond comments within the code.
   - Always check that your code is runnable and produces the intended animation.

### Final Template:
```python
from manim import *


class YourAnimation(Scene):
    def construct(self):
        # Your animation code here
        pass


if __name__ == "__main__":
    scene = YourAnimation()
    scene.render()
```

Follow these instructions meticulously to ensure your Manim code is syntactically and structurally correct, requiring no modifications before rendering.  

---  

**Note**: If you find that certain concepts require complex code, generate one animation at a time, focusing on clarity over completeness. Do not overcomplicate the code unless explicitly requested.
"""

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
        
        # Clean out any thinking process
        result = clean_thinking_output(result)
        
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
        logger.info(f"Improving prompt of length {len(prompt)}")
        
        # Simplified system prompt to reduce memory usage
        system_prompt = """
As an assistant specializing in creating Manim 2D math animation code, your role is to refine and enhance the user's initial prompt, ensuring it's both clear and comprehensive. Here's how you'll proceed:

### 1. Understand the User's Intent:
   - Carefully analyze the user's original prompt to grasp they're trying to achieve with their animation.
   - Identify key elements such as the mathematical concepts, visual effects, and animation sequences they're interested in.

### 2. Identify Ambiguities and Missing Details:
   - Pinpoint any parts of the prompt that are vague or lack specificity. This could include unspecified animations, unclear mathematical operations, or incomplete descriptions of visual elements.
   - Determine what additional information is necessary to create a complete and functional Manim animation.

### 3. Integrate User's Answers:
   - Once hypothetical answers are provided, integrate this new information back into the refined prompt.
   - Ensure that the revised prompt is detailed, specific, and includes all necessary components for generating the desired animation.

### 4. Provide the Revised Prompt:
   - Present the user with a clear and enhanced version of their original prompt, incorporating all new details and specifications.
   - The revised prompt should be structured to directly guide the creation of code in the Manim library, minimizing ambiguity and ensuring all intended elements are included.

### Final Task:
   - DO NOT INCLUDE THE USER"S ORIGINAL PROMPT
   - DO NOT GENERATE CODE JUST GENERATE AN IMRPOVISED PROMPT
   - Take the given user's prompt and enrich it with all gathered information and specifics.
   - Ensure the refined prompt is ready to be turned into a detailed and accurate Manim animation code, with no room for misinterpretation.
   - Remember, your goal is to help the user articulate their vision in a way that allows for seamless translation into functional Manim code, focusing solely on generating the refined prompt.
"""
        
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
            
            improved = accumulated_response
            
        except Exception as api_error:
            logger.error(f"Error during OpenAI API call for prompt improvement: {str(api_error)}")
            logger.error(traceback.format_exc())
            improved = f"Error improving prompt: {str(api_error)}. Please try again with a simpler description."
        
        # Remove any thinking markers from the improved prompt
        improved = re.sub(r'(?i)#+ ?thinking:?.*?(\n|$)', '', improved)
        improved = re.sub(r'(?i)#+ ?reasoning:?.*?(\n|$)', '', improved)
        
        # If there are section headings with ##, only keep the final output
        if "##" in improved:
            sections = improved.split("##")
            # Get the last non-empty section
            for section in reversed(sections):
                if section.strip():
                    improved = section.strip()
                    break
        
        # Force garbage collection
        force_gc()
        
        logger.info(f"Successfully improved prompt from {len(prompt)} to {len(improved)} chars")
        return improved.strip()
        
    except Exception as e:
        logger.error(f"Error in improve_prompt: {str(e)}")
        logger.error(traceback.format_exc())
        force_gc()
        raise Exception(f"Failed to improve prompt: {str(e)}")