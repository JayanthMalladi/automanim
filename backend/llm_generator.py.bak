import langchain
from openai import OpenAI
from langchain_openai.chat_models.base import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API credentials from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_BASE = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek/deepseek-prover-v2:free")

def generate_manim_code(prompt):
    try:
        system_template = """
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
        systemMessage = SystemMessagePromptTemplate.from_template(system_template)
        human_template = "Question : {question}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)
        chat_prompt = ChatPromptTemplate.from_messages([systemMessage, human_message])

        llm = ChatOpenAI(
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base=OPENROUTER_API_BASE,
            model_name=DEFAULT_MODEL
        )

        llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
        response = llm_chain.run({"question": prompt})

        # Optionally, strip markdown code block markers
        if response.startswith("```python"):
            response = response[len("```python"):].strip()
        if response.endswith("```"):
            response = response[:-3].strip()

        return response

    except Exception as e:
        return f"// Error generating code: {str(e)}"
    

def improve_prompt(prompt):
    print("improve_prompt function called")
    try: 
        system_template = """
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
        system_message = SystemMessagePromptTemplate.from_template(system_template)

        human_template = "Prompt: {prompt}"
        human_message = HumanMessagePromptTemplate.from_template(human_template)

        chat_prompt = ChatPromptTemplate.from_messages([system_message,human_message])
        llm = ChatOpenAI(
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base=OPENROUTER_API_BASE,
            model_name=DEFAULT_MODEL
        )

        llm_chain = LLMChain(prompt=chat_prompt, llm=llm)
        improved = llm_chain.run({"prompt": prompt})
        return improved.strip()
    except Exception as e:
        print(f"Error in improve_prompt: {str(e)}")
        raise Exception(f"Failed to improve prompt: {str(e)}")