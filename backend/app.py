from flask import Flask, request, jsonify
from flask_cors import CORS
from llm_generator import generate_manim_code
from llm_generator import improve_prompt


app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "https://*.vercel.app", "https://*.your-domain.com"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

@app.route('/generate' , methods = ['POST'])
def generate():
    data = request.get_json()
    prompt = data.get('prompt' ,'')
    code = generate_manim_code(prompt)
    return jsonify({'code' : code} )


@app.route('/improve_prompt', methods=['POST'])
def improve_prompt_route():
    try:
        print("Received improve prompt request")
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        prompt = data.get('prompt', '')
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400
            
        print(f"Prompt received: {prompt}")
        improved = improve_prompt(prompt)
        print(f"Improved prompt: {improved}")
        return jsonify({'improved_prompt': improved})
    except Exception as e:
        print(f"Error in improve_prompt_route: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(port = 5000)