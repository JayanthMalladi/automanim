import langchain
from openai import OpenAI
from langchain_openai import ChatOpenAI  # Updated import
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
import os
import gc
import logging
import resource
import time
import traceback
import psutil
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

# Global LLM instance
_llm_instance = None

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

def get_llm():
    """Lazy-load the LLM instance only when needed"""
    global _llm_instance
    if _llm_instance is None:
        try:
            _llm_instance = ChatOpenAI(
                openai_api_key=OPENROUTER_API_KEY,
                openai_api_base=OPENROUTER_API_BASE,
                model_name=DEFAULT_MODEL,
                request_timeout=300  # Increase timeout to 5 minutes
            )
            logger.info("LLM instance created successfully")
        except Exception as e:
            logger.error(f"Error creating LLM instance: {str(e)}")
            raise
    return _llm_instance

def generate_manim_code(prompt):
    start_time = time.time()
    log_memory_usage()
    
    try:
        # Trim prompt if it's too long - more aggressive trimming to save memory
        max_prompt_length = 4000  # Limit max prompt length
        if len(prompt) > max_prompt_length:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to {max_prompt_length} chars")
            prompt = prompt[:max_prompt_length]
            
        logger.info(f"Generating Manim code for prompt of length {len(prompt)}")
        
        system_template = """
You are an expert AI specialized in generating complete, production-ready Manim code for creating educational animations, similar to those seen in 3Blue1Brown's videos. Your primary objective is to provide clean, functional, and fully executable Manim code without placeholders, TODOs, or partial implementations.

### Instructions:
1. **Imports**: Start by importing all necessary modules from the Manim library (`from manim import *`). Include any other required Python libraries (numpy, math, etc.) needed for the animation.

2. **Code Structure**:
   - Create a class that inherits from `Scene` with a descriptive name related to the animation content.
   - Implement a complete `construct` method with all functionality fully implemented.
   - Include any helper methods needed to organize the code and avoid repetition.
   - Wrap the code with `if __name__ == "__main__":` and include the render call.
   - Use proper error handling when appropriate.

3. **COMPLETE Implementation Requirements**:
   - NEVER use placeholder comments like "TODO", "implement this", or similar phrases.
   - ALWAYS fully implement all functionality mentioned in the prompt.
   - Break complex animations into manageable steps with clear transitions.
   - Include all mathematical formulas, visual elements, and animations requested.
   - For complex animations, create helper functions rather than leaving parts incomplete.
   - If something seems ambiguous, make reasonable assumptions and implement it fully rather than leaving it incomplete.

4. **Best Practices**:
   - Use the latest version of Manim Community conventions (v0.18.0+).
   - Use LaTeX (`MathTex`, `Tex`) for all mathematical expressions.
   - Implement smooth transitions and proper animation timing.
   - Include appropriate wait times between animation steps.
   - Use color, positioning, and scaling to create visually appealing animations.
   - Add camera movements when appropriate for dynamic animations.

5. **Output Format**:
   - Provide ONLY the complete Python code, ready to be executed with manim.
   - DO NOT include triple backticks or explanations outside the code.
   - Include helpful comments within the code to explain the animation flow.
   - Ensure class and function names are descriptive and follow PEP8 naming conventions.

Remember: Your output will be directly executed by users, so it must be COMPLETE, EXECUTABLE, and FULLY IMPLEMENTED. Do not leave any part of the animation as an exercise for the user.

### Complete Working Template:
```python
from manim import *
import numpy as np  # Import additional libraries as needed

class YourAnimation(Scene):
    def construct(self):
        # Complete implementation of the animation
        # No TODOs or placeholders allowed
        
        # Example of fully implemented animation
        title = Title("Complete Animation")
        self.play(Write(title))
        
        # Mathematical expression with full implementation
        formula = MathTex(r"f(x) = x^2 + 2x + 1")
        self.play(Write(formula))
        
        # Make sure timing is appropriate
        self.wait(1)
        
        # Example of a transformation with complete implementation
        new_formula = MathTex(r"f(x) = (x + 1)^2")
        self.play(TransformMatchingTex(formula, new_formula))
        self.wait(2)

if __name__ == "__main__":
    scene = YourAnimation()
    scene.render()
```

Always verify that your code is syntactically correct, handles all edge cases, and fully implements the requested animation without any placeholders or TODO comments."""
        systemMessage = SystemMessagePromptTemplate.from_template(system_template)
        human_template = "Question : {question}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)
        
        # Use a shorter version for complex prompts to save memory
        if len(prompt) > 1500:
            logger.info("Using shorter system template to save memory")
            system_template = """
Generate complete, ready-to-run Manim code for an educational animation. Include all imports, necessary functions, and implement ALL requirements fully without TODOs or placeholders. Keep code clean, efficient, and follow best practices.

IMPORTANT:
- Use `from manim import *` and any other needed imports
- Create a complete Scene class with a thorough construct method
- Fully implement all requested features with NO placeholders
- Include proper timing with self.wait() between animation steps
- Use descriptive comments to explain the steps
- Make it directly executable with the render call at the end
"""
            systemMessage = SystemMessagePromptTemplate.from_template(system_template)
        
        chat_prompt = ChatPromptTemplate.from_messages([systemMessage, human_message])

        # Log memory usage at key points
        log_memory_usage()
        
        # Use a timeout to prevent hanging
        llm = get_llm()
        
        # Create a new chain for each request to avoid memory leaks
        llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
        
        # Set resource limits to avoid memory issues
        # soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        # resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 * 1024 * 1024, hard))  # 4 GB memory limit
        
        logger.info("Sending request to LLM API")
        try:
            response = llm_chain.invoke({"question": prompt})
            logger.info("Response received from LLM API")
            
            # Extract the text from the response object and clear references
            if isinstance(response, dict) and "text" in response:
                result = response["text"]
                # Clear references
                response.clear()
            else:
                result = str(response)

            # Optionally, strip markdown code block markers
            if result.startswith("```python"):
                result = result[len("```python"):].strip()
            if result.endswith("```"):
                result = result[:-3].strip()
                
            # Check if the result is empty or too short (likely an error)
            if len(result) < 50:
                logger.warning(f"Generated code is suspiciously short ({len(result)} chars)")
                if len(result) < 10:
                    result = "# Error: Generated code was too short or empty. Please try again with a simpler prompt."
        except Exception as e:
            logger.error(f"Error during LLM invocation: {str(e)}")
            result = f"# Error during code generation: {str(e)}\n# Please try again with a simpler prompt."
            
        # Force garbage collection to free memory
        chat_prompt = None
        llm_chain = None
        systemMessage = None
        human_message = None
        force_gc()
        
        process_time = time.time() - start_time
        logger.info(f"Successfully generated code of length {len(result)} in {process_time:.2f} seconds")
        return result

    except Exception as e:
        logger.error(f"Error generating code: {str(e)}", exc_info=True)
        logger.error(traceback.format_exc())
        force_gc()  # Try to free memory even on failure
        return f"// Error generating code: {str(e)}"
    

def improve_prompt(prompt):
    logger.info("improve_prompt function called")
    log_memory_usage()
    
    try: 
        # Trim prompt if it's too long - more aggressive trimming to save memory
        max_prompt_length = 4000  # Limit max prompt length
        if len(prompt) > max_prompt_length:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to {max_prompt_length} chars")
            prompt = prompt[:max_prompt_length]
            
        system_template = """
As an expert assistant specializing in Manim animation code, your task is to transform vague or incomplete user prompts into highly detailed, specific instructions that will result in fully-implemented animation code with no TODOs or placeholders.

### Your Transformation Process:

### 1. Expand the Animation Scope:
   - Identify the core animation concept in the user's prompt
   - Add specific details about the visual elements that should appear (shapes, equations, text, etc.)
   - Specify exact animations (fading, morphing, moving along paths, etc.)
   - Include timing details (duration, pauses between steps)
   - Add color specifications, positioning, and stylistic elements
   - Ensure all mathematical notations or formulas are completely defined

### 2. Technical Specifications:
   - Include specific Manim objects to use (Circle, Square, MathTex, Axes, etc.)
   - Specify animation methods (Create, Write, Transform, MoveAlongPath, etc.)
   - Include details about camera movements if relevant
   - Suggest specific coordinates or layouts
   - Mention any required mathematical functions or transformations
   - Include specific colors, sizes, and styling parameters

### 3. Animation Sequence and Flow:
   - Break down the animation into clear sequential steps
   - Specify transitions between different elements
   - Define how mathematical concepts should evolve or transform
   - Ensure logical progression in educational content
   - Include specific wait times between key animation points
   - Define how complex elements should be built up step-by-step

### 4. Provide a Complete Animation Blueprint:
   - Structure your response as a clear, detailed specification
   - Include all necessary information for implementation without guesswork
   - Eliminate any ambiguities that could lead to placeholder code
   - Provide specific values for parameters where needed (coordinates, sizes, colors, durations)
   - Ensure each animation step is fully described with Manim terminology

### Important Guidelines:
   - DO NOT GENERATE CODE - only produce a detailed prompt
   - DO NOT include the user's original prompt verbatim
   - FOCUS on adding specific implementation details that eliminate the need for placeholders
   - ASSUME the animation will be implemented exactly as you describe, so be comprehensive
   - ENSURE your prompt would lead to code with no TODOs or "implement this later" comments
   - Use proper Manim terminology that aligns with the latest Manim Community version

Your goal is to create a prompt so detailed and specific that it eliminates any need for the developer to make significant decisions or leave parts unimplemented due to ambiguity."""
        system_message = SystemMessagePromptTemplate.from_template(system_template)

        # For longer prompts, use a simpler system message to save memory
        if len(prompt) > 1500:
            logger.info("Using shorter system template to save memory")
            system_template = """
Transform vague animation prompts into detailed specifications that can be fully implemented.

Make sure to:
1. Add specific visual elements, animations, and timing
2. Include technical details (objects, methods, coordinates)
3. Specify the sequence of animation steps
4. Eliminate all ambiguity that could lead to incomplete implementations

DO NOT generate code - provide a comprehensive blueprint using proper Manim terminology.
"""
            system_message = SystemMessagePromptTemplate.from_template(system_template)

        human_template = "Prompt: {prompt}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)

        chat_prompt = ChatPromptTemplate.from_messages([system_message, human_message])
        
        # Log memory usage at key points
        log_memory_usage()
        
        # Use the lazily loaded LLM
        llm = get_llm()

        # Create a new chain for each request
        llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
        
        logger.info("Sending request to LLM API for prompt improvement")
        try:
            response = llm_chain.invoke({"prompt": prompt})
            logger.info("Response received from LLM API")
            
            # Extract the text from the response object
            if isinstance(response, dict) and "text" in response:
                improved = response["text"]
                # Clear references
                response.clear()
            else:
                improved = str(response)
                
            # Check if result is too short (likely an error)
            if len(improved) < 50:
                logger.warning(f"Improved prompt is suspiciously short ({len(improved)} chars)")
                if len(improved) < 10:
                    improved = "Error: Could not improve the prompt. Please try with a different description."
        except Exception as e:
            logger.error(f"Error during LLM invocation for prompt improvement: {str(e)}")
            improved = f"Error improving prompt: {str(e)}. Please try again with a simpler description."
            
        # Clear references to help with garbage collection
        chat_prompt = None
        llm_chain = None
        system_message = None
        human_message = None
        force_gc()
        
        logger.info(f"Successfully improved prompt from {len(prompt)} to {len(improved)} chars")
        return improved.strip()
    except Exception as e:
        logger.error(f"Error in improve_prompt: {str(e)}", exc_info=True)
        logger.error(traceback.format_exc())
        force_gc()  # Try to free memory even on failure
        raise Exception(f"Failed to improve prompt: {str(e)}")