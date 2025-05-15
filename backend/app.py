from flask import Flask, request, jsonify
from flask_cors import CORS
from llm_generator import generate_manim_code
from llm_generator import improve_prompt
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# More permissive CORS configuration
CORS(app, 
     resources={r"/*": {"origins": "*"}}, 
     supports_credentials=False,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])

@app.route('/generate' , methods = ['POST'])
def generate():
    try:
        # Log request information
        logger.info(f"Received generate request from origin: {request.headers.get('Origin', 'Unknown')}")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in generate endpoint")
            return jsonify({'error': 'No JSON data received'}), 400
            
        prompt = data.get('prompt', '')
        if not prompt:
            logger.error("No prompt provided in generate endpoint")
            return jsonify({'error': 'No prompt provided'}), 400
            
        logger.info(f"Processing prompt: {prompt[:50]}...")
        code = generate_manim_code(prompt)
        logger.info("Successfully generated code")
        return jsonify({'code': code})
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}", exc_info=True)
        return jsonify({'error': str(e), 'code': f"// Error generating code: {str(e)}"}), 500


@app.route('/improve_prompt', methods=['POST'])
def improve_prompt_route():
    try:
        logger.info(f"Received improve_prompt request from origin: {request.headers.get('Origin', 'Unknown')}")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in improve_prompt endpoint")
            return jsonify({'error': 'No JSON data received'}), 400
        
        prompt = data.get('prompt', '')
        if not prompt:
            logger.error("No prompt provided in improve_prompt endpoint")
            return jsonify({'error': 'No prompt provided'}), 400
            
        logger.info(f"Processing prompt for improvement: {prompt[:50]}...")
        improved = improve_prompt(prompt)
        logger.info(f"Successfully improved prompt: {improved[:50]}...")
        return jsonify({'improved_prompt': improved})
    except Exception as e:
        logger.error(f"Error in improve_prompt_route: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(port = 5000)