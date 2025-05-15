from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
import time
import gc
import psutil
from llm_generator import generate_manim_code, improve_prompt, force_gc, log_memory_usage

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Request tracking variables
request_count = 0
active_requests = 0

@app.before_request
def before_request():
    """Log memory usage before each request"""
    global request_count, active_requests
    request_count += 1
    active_requests += 1
    logger.info(f"Request #{request_count} started. Active requests: {active_requests}")
    force_gc()  # Force garbage collection before each request
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logger.info(f"[REQUEST START] Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")
    request.start_time = time.time()

@app.after_request
def after_request(response):
    """Log request duration and memory usage after each request"""
    global active_requests
    active_requests -= 1
    logger.info(f"Request completed. Active requests: {active_requests}")
    duration = time.time() - request.start_time
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logger.info(f"[REQUEST END] Duration: {duration:.2f}s - Memory: {mem_info.rss / 1024 / 1024:.2f} MB")
    force_gc()  # Force garbage collection after each request
    return response

@app.route('/api/improve_prompt', methods=['POST'])
def improve_prompt_route():
    """API endpoint to improve an animation prompt"""
    start_time = time.time()
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400

        prompt_text = data['prompt']
        logger.info(f"Received improve_prompt request with {len(prompt_text)} chars")
        
        if len(prompt_text.strip()) < 5:
            return jsonify({'error': 'Prompt too short'}), 400
        
        # Log memory usage
        log_memory_usage()
        
        # Call the LLM to improve the prompt
        improved_prompt = improve_prompt(prompt_text)
        
        # Log processing time and memory
        process_time = time.time() - start_time
        logger.info(f"improve_prompt processed in {process_time:.2f} seconds")
        log_memory_usage()
        
        return jsonify({'improved_prompt': improved_prompt})
    
    except Exception as e:
        logger.error(f"Error in improve_prompt endpoint: {str(e)}", exc_info=True)
        force_gc()  # Force GC on error
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate():
    """API endpoint to generate Manim code"""
    start_time = time.time()
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400

        prompt_text = data['prompt']
        logger.info(f"Received generation request with {len(prompt_text)} chars")
        
        if len(prompt_text.strip()) < 5:
            return jsonify({'error': 'Prompt too short'}), 400
        
        # Log memory usage
        log_memory_usage()
        
        # Call the LLM to generate Manim code
        manim_code = generate_manim_code(prompt_text)
        
        # Log processing time and memory
        process_time = time.time() - start_time
        logger.info(f"Generation processed in {process_time:.2f} seconds")
        log_memory_usage()
        
        return jsonify({'manim_code': manim_code})
    
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}", exc_info=True)
        force_gc()  # Force GC on error
        return jsonify({'error': str(e)}), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return jsonify({
        'status': 'healthy', 
        'memory_usage_mb': memory_info.rss / 1024 / 1024,
        'active_requests': active_requests,
        'total_requests': request_count,
        'uptime': time.time()
    })

# Stats endpoint for more detailed metrics
@app.route('/api/stats', methods=['GET'])
def stats():
    """More detailed stats endpoint"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    return jsonify({
        'memory_usage_mb': memory_info.rss / 1024 / 1024,
        'cpu_percent': process.cpu_percent(),
        'active_requests': active_requests,
        'total_requests': request_count,
        'threads': len(process.threads()),
        'open_files': len(process.open_files()),
        'connections': len(process.connections())
    })

if __name__ == '__main__':
    # Force garbage collection at startup
    force_gc()
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
