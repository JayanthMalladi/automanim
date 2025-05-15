from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
import time
import gc
import psutil
import threading
from datetime import datetime, timedelta
from collections import defaultdict
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

# User rate limiting - track when each user last made a request
user_last_request = defaultdict(lambda: datetime.min)
COOLDOWN_SECONDS = 120  # Time in seconds before a user can make another request

def get_user_id():
    """Get a unique identifier for the current user"""
    # IP address is a basic way to identify users
    return request.remote_addr or request.headers.get('X-Forwarded-For', 'unknown')

@app.before_request
def before_request():
    """Log memory usage before each request and check for rate limiting"""
    # Skip rate limiting for non-API routes
    if not request.path.startswith('/api/improve_prompt') and not request.path.startswith('/api/generate'):
        return
    
    # Check if the user is on cooldown
    user_id = get_user_id()
    last_request_time = user_last_request[user_id]
    time_since_last = datetime.now() - last_request_time
    
    if time_since_last < timedelta(seconds=COOLDOWN_SECONDS):
        time_remaining = COOLDOWN_SECONDS - time_since_last.total_seconds()
        logger.info(f"Rate limit hit for user {user_id}. {time_remaining:.0f} seconds remaining.")
        return jsonify({
            'error': 'Rate limit exceeded',
            'message': f'Please wait {time_remaining:.0f} seconds before making another request',
            'time_remaining': int(time_remaining)
        }), 429
        
    # Proceed with the request if no rate limiting issues
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
    # Only update the last request time for API endpoints that need rate limiting
    if request.path.startswith('/api/improve_prompt') or request.path.startswith('/api/generate'):
        # Update the last request time for the user
        user_id = get_user_id()
        user_last_request[user_id] = datetime.now()
    
    # Standard logging and cleanup
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
        
        # Hide the thinking process by only returning the final result
        if "##" in improved_prompt:
            # If there's a section marker, only return content after the last ##
            sections = improved_prompt.split("##")
            improved_prompt = sections[-1].strip()
        
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
        
        # Hide the thinking process by ensuring we only show the final code
        # Remove any comments that might be part of the thinking process
        if "# Thinking:" in manim_code:
            manim_code = manim_code.split("# Thinking:")[0].strip()
        
        # Strip any markdown formatting that might remain
        if "```python" in manim_code:
            manim_code = manim_code.replace("```python", "").replace("```", "").strip()
        
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
        'connections': len(process.connections()),
        'active_users': len(user_last_request)
    })

# Cooldown status endpoint
@app.route('/api/cooldown_status', methods=['GET'])
def cooldown_status():
    """Check if a user is on cooldown and how much time remains"""
    user_id = get_user_id()
    last_request_time = user_last_request[user_id]
    time_since_last = datetime.now() - last_request_time
    
    if time_since_last < timedelta(seconds=COOLDOWN_SECONDS):
        time_remaining = COOLDOWN_SECONDS - time_since_last.total_seconds()
        return jsonify({
            'on_cooldown': True,
            'time_remaining': int(time_remaining)
        })
    else:
        return jsonify({
            'on_cooldown': False,
            'time_remaining': 0
        })

if __name__ == '__main__':
    # Force garbage collection at startup
    force_gc()
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
