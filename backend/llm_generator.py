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

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL")

# Global LLM instance
_llm_instance = None

def get_llm():
    """Lazy-load the LLM instance only when needed"""
    global _llm_instance
    if _llm_instance is None:
        try:
            _llm_instance = ChatOpenAI(
                openai_api_key=OPENROUTER_API_KEY,
                openai_api_base=OPENROUTER_API_BASE,
                model_name=DEFAULT_MODEL,
                request_timeout=180  # Increase timeout
            )
            logger.info("LLM instance created successfully")
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
        chat_prompt = ChatPromptTemplate.from_messages([systemMessage, human_message])

        # Use the lazily loaded LLM
        llm = get_llm()

        # Create a new chain for each request to avoid memory leaks
        llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
        response = llm_chain.invoke({"question": prompt})

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

        # Force garbage collection to free memory
        chat_prompt = None
        llm_chain = None
        gc.collect()
        
        logger.info(f"Successfully generated code of length {len(result)}")
        return result

    except Exception as e:
        logger.error(f"Error generating code: {str(e)}", exc_info=True)
        gc.collect()  # Try to free memory even on failure
        return f"// Error generating code: {str(e)}"
    

def improve_prompt(prompt):
    logger.info("improve_prompt function called")
    try: 
        # Trim prompt if it's too long
        if len(prompt) > 5000:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to 5000 chars")
            prompt = prompt[:5000]
            
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

        human_template = "Prompt: {prompt}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)

        chat_prompt = ChatPromptTemplate.from_messages([system_message, human_message])
        
        # Use the lazily loaded LLM
        llm = get_llm()

        # Create a new chain for each request
        llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
        response = llm_chain.invoke({"prompt": prompt})
        
        # Extract the text from the response object
        if isinstance(response, dict) and "text" in response:
            improved = response["text"]
            # Clear references
            response.clear()
        else:
            improved = str(response)
            
        # Clear references to help with garbage collection
        chat_prompt = None
        llm_chain = None
        gc.collect()
        
        logger.info(f"Successfully improved prompt of length {len(improved)}")
        return improved.strip()
    except Exception as e:
        logger.error(f"Error in improve_prompt: {str(e)}", exc_info=True)
        gc.collect()  # Try to free memory even on failure
        raise Exception(f"Failed to improve prompt: {str(e)}")