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
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek/deepseek-prover-v2:free")

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

def generate_manim_code(prompt, conversation_history=None):
    try:
        # Trim prompt if it's too long
        if len(prompt) > 5000:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to 5000 chars")
            prompt = prompt[:5000]
            
        logger.info(f"Generating Manim code for prompt of length {len(prompt)}")
        
        system_template = """
You are an AI specialized in generating complete and FULLY IMPLEMENTED Manim code for educational animations. Your primary responsibility is to write comprehensive, runnable code that includes ALL functionality requested by the user without any placeholders, TODOs, or incomplete sections.

### MANDATORY REQUIREMENTS:
1. **COMPLETE IMPLEMENTATION**: You must fully implement all functionality requested by the user. Never leave any part as a placeholder or TODO comment.

2. **IMPORTS**:
   - ALWAYS start with `from manim import *`
   - Include any other necessary imports for functionality (numpy, math, etc.)

3. **CODE STRUCTURE**:
   - Define a descriptively named class inheriting from Scene
   - Implement a comprehensive construct() method with ALL requested features
   - ALWAYS include the if __name__ == "__main__" block with scene instantiation and render call
   - Use proper 4-space indentation throughout

4. **ANIMATIONS**:
   - Include all animations specified in the prompt
   - Use self.play() for proper animation sequencing
   - Set appropriate timing with run_time parameters
   - Implement complex animations step by step
   - Ensure smooth transitions between animation steps

5. **MATHEMATICAL CONTENT**:
   - Use MathTex for LaTeX mathematical expressions
   - Fully implement all formulas, equations, or mathematical concepts mentioned in the prompt
   - Add appropriate labels, colors, and positioning

6. **QUALITY STANDARDS**:
   - Use descriptive variable names
   - Include helpful comments explaining logic
   - Ensure all objects are properly positioned and visible
   - Handle edge cases and potential errors
   - Test the conceptual flow of your code for logical errors

### ABSOLUTELY FORBIDDEN:
- NO placeholders or "# TODO" comments
- NO incomplete implementations
- NO skeleton code requiring further work
- NO "pass" statements in place of actual functionality
- NO missing features mentioned in the user's request

### TEMPLATE STRUCTURE (customize with COMPLETE implementation):
```python
from manim import *
# Add any other necessary imports

class DescriptiveNameForAnimation(Scene):
    def construct(self):
        # FULLY IMPLEMENT all requested animations here
        # Do not use placeholders or TODOs
        
        # Example of proper implementation (replace with actual implementation):
        equation = MathTex("E = mc^2")
        self.play(Write(equation), run_time=1)
        self.wait(1)

if __name__ == "__main__":
    scene = DescriptiveNameForAnimation()
    scene.render()
```

Remember: The user expects COMPLETE, RUNNABLE code with EVERY feature implemented. Your code should work when copied directly into a Python file with Manim installed.
"""
        systemMessage = SystemMessagePromptTemplate.from_template(system_template)
        
        messages = [systemMessage]
        
        # Add conversation history if provided
        if conversation_history and len(conversation_history) > 0:
            logger.info(f"Using conversation history with {len(conversation_history)} messages")
            for msg in conversation_history:
                if msg["type"] == "user":
                    messages.append(HumanMessagePromptTemplate.from_template(
                        f"User's previous request: {msg['content']}"
                    ))
                elif msg["type"] == "assistant":
                    # For assistant messages, we'll add them as system messages to maintain context
                    messages.append(SystemMessagePromptTemplate.from_template(
                        f"Your previous code generation: {msg['content']}"
                    ))
        
        # Add the current prompt as the final human message
        human_template = "Generate COMPLETE, FULLY IMPLEMENTED Manim code for the following (implement everything, no TODOs or placeholders): {question}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)
        messages.append(human_message)
        
        # Create the chat prompt with all messages
        chat_prompt = ChatPromptTemplate.from_messages(messages)

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
You are a specialized Manim animation prompt enhancement expert. Your task is to transform vague user requests into comprehensive, precise, and detailed prompts that will lead to complete and functional Manim animations. 

### YOUR PROCESS (FOLLOW STRICTLY):

1. **ANALYZE THE USER'S REQUEST**:
   - Identify the core animation concept or mathematical idea
   - Determine what visual elements are needed
   - Note any specific animations, transitions, or effects mentioned
   - Identify any missing but necessary details

2. **PROVIDE COMPREHENSIVE DETAILS** for each of these aspects:
   - **Visual Elements**: Specify exact objects (shapes, equations, graphs, etc.), their initial properties (color, size, position), and how they should appear
   - **Animation Sequence**: Detail the precise order of animations, what happens to each object, and how transitions occur
   - **Timing**: Specify appropriate durations for each animation step and pauses between sections
   - **Mathematical Content**: Expand mathematical expressions, formulas, or concepts with exact notation and steps
   - **Visual Style**: Specify colors, layout, backgrounds, and aesthetic elements
   - **Camera Work**: Include any camera movements, zooms, or perspective changes

3. **ADD TECHNICAL SPECIFICATIONS**:
   - Mention specific Manim functions and methods that would be useful (Create, Write, Transform, etc.)
   - Suggest appropriate MathTex formatting for equations
   - Recommend specific techniques for complex effects
   - Include guidance on object positioning and scene composition

4. **COMPLETE ALL DETAILS** - leave NOTHING to interpretation:
   - No ambiguous descriptions
   - No undefined variables or objects
   - No vague animation suggestions
   - No undefined mathematical operations

### CRITICAL REQUIREMENTS:
- Do NOT include any code in your response
- Do NOT use the phrase "the animation should" - instead be specific about what MUST be implemented
- Do NOT merely paraphrase the original prompt - EXPAND it significantly with precise details
- Do NOT say "depending on preference" - make definitive choices for the best visual result
- Do NOT include the original prompt verbatim

### FORMAT YOUR RESPONSE:
- Use clear, concise language organized into logical sections
- Number the animation steps in sequence
- Bold or emphasize key elements and important details
- Be comprehensive but focused - every detail should serve the animation goal

Your improved prompt should be so clear and detailed that it leads to a complete, polished Manim animation with no undefined aspects or missing elements.
"""
        system_message = SystemMessagePromptTemplate.from_template(system_template)

        human_template = "Original prompt: {prompt}\n\nPlease transform this into a comprehensive, detailed, and precise Manim animation prompt:"
        human_message = HumanMessagePromptTemplate.from_template(human_template)

        chat_prompt = ChatPromptTemplate.from_messages([system_message,human_message])
        
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