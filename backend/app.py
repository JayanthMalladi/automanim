from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from llm_generator import generate_manim_code, improve_prompt, log_memory_usage, force_gc
import logging
import gc
import time
import threading
import signal
import os
import traceback
import psutil
from functools import wraps

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s [%(levelname)s] %(message)s',
                   handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Configure timeout for hanging requests
TIMEOUT_SECONDS = 300
MAX_PROMPT_LENGTH = 4000  # Maximum prompt length to accept
MAX_CODE_SIZE = 100 * 1024  # Maximum size of returned code (100 KB)

def timeout_handler(signum, frame):
    logger.error("Request processing timed out")
    gc.collect()
    raise TimeoutError("Request took too long to process")

# Request timeout decorator
def timeout_decorator(seconds):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set the timeout handler
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
                # Cancel the alarm if the function returns
                signal.alarm(0)
                return result
            except Exception as e:
                # Cancel the alarm if an exception is raised
                signal.alarm(0)
                raise e
        return wrapper
    return decorator

app = Flask(__name__)
# More permissive CORS configuration
CORS(app, 
     resources={r"/*": {"origins": "*"}}, 
     supports_credentials=False,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"])

# Add request tracking for diagnostics
request_count = 0
active_requests = 0

@app.before_request
def before_request():
    global request_count, active_requests
    request_count += 1
    active_requests += 1
    logger.info(f"Request #{request_count} started. Active requests: {active_requests}")
    log_memory_usage()

@app.after_request
def after_request(response):
    global active_requests
    active_requests -= 1
    logger.info(f"Request completed. Active requests: {active_requests}")
    force_gc()  # Force garbage collection after each request
    return response

@app.route('/generate', methods=['POST'])
@timeout_decorator(TIMEOUT_SECONDS)
def generate():
    start_time = time.time()
    try:
        # Log request information
        logger.info(f"Received generate request from origin: {request.headers.get('Origin', 'Unknown')}")
        
        # Get JSON data - limit content length
        if request.content_length and request.content_length > MAX_PROMPT_LENGTH * 2:  # Allow some overhead
            logger.error(f"Request too large: {request.content_length} bytes")
            return jsonify({'error': 'Request too large', 'code': '// Error: Your prompt is too large. Please simplify it.'}), 413
            
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in generate endpoint")
            return jsonify({'error': 'No JSON data received'}), 400
            
        prompt = data.get('prompt', '')
        if not prompt:
            logger.error("No prompt provided in generate endpoint")
            return jsonify({'error': 'No prompt provided'}), 400
            
        # Limit prompt size
        if len(prompt) > MAX_PROMPT_LENGTH:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to {MAX_PROMPT_LENGTH}")
            prompt = prompt[:MAX_PROMPT_LENGTH]
            
        logger.info(f"Processing prompt: {prompt[:50]}...")
        
        # Measure memory before generation
        before_mem = log_memory_usage()
        
        # Generate code with a separate try/except to handle specific generation errors
        try:
            code = generate_manim_code(prompt)
        except Exception as gen_error:
            logger.error(f"Error in code generation: {str(gen_error)}", exc_info=True)
            # Return a friendly error message
            return jsonify({
                'error': 'Code generation failed',
                'code': f"// Error generating code: {str(gen_error)}\n// Please try again with a simpler prompt."
            }), 500
            
        # Limit response size
        if len(code) > MAX_CODE_SIZE:
            logger.warning(f"Generated code too large ({len(code)} bytes), truncating")
            code = code[:MAX_CODE_SIZE] + "\n\n# Note: Code was truncated due to size limits"
            
        processing_time = time.time() - start_time
        logger.info(f"Successfully generated code in {processing_time:.2f} seconds")
        
        # Memory usage after generation
        after_mem = log_memory_usage()
        logger.info(f"Memory usage for generation: {after_mem - before_mem:.2f} MB")
        
        force_gc()  # Clean up memory
        return jsonify({'code': code})
    except TimeoutError as e:
        logger.error(f"Request timed out: {str(e)}")
        force_gc()  # Try to clean up memory
        return jsonify({'error': 'Request timed out', 'code': '// Error: The request took too long to process. Please try with a simpler prompt.'}), 408
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}", exc_info=True)
        logger.error(traceback.format_exc())
        force_gc()  # Try to clean up memory
        return jsonify({'error': str(e), 'code': f"// Error generating code: {str(e)}"}), 500


@app.route('/improve_prompt', methods=['POST'])
@timeout_decorator(TIMEOUT_SECONDS)
def improve_prompt_route():
    start_time = time.time()
    try:
        logger.info(f"Received improve_prompt request from origin: {request.headers.get('Origin', 'Unknown')}")
        
        # Get JSON data - limit content length
        if request.content_length and request.content_length > MAX_PROMPT_LENGTH * 2:  # Allow some overhead
            logger.error(f"Request too large: {request.content_length} bytes")
            return jsonify({'error': 'Request too large'}), 413
        
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in improve_prompt endpoint")
            return jsonify({'error': 'No JSON data received'}), 400
        
        prompt = data.get('prompt', '')
        if not prompt:
            logger.error("No prompt provided in improve_prompt endpoint")
            return jsonify({'error': 'No prompt provided'}), 400
            
        # Limit prompt size
        if len(prompt) > MAX_PROMPT_LENGTH:
            logger.warning(f"Prompt too long ({len(prompt)} chars), trimming to {MAX_PROMPT_LENGTH}")
            prompt = prompt[:MAX_PROMPT_LENGTH]
            
        logger.info(f"Processing prompt for improvement: {prompt[:50]}...")
        
        # Measure memory before improvement
        before_mem = log_memory_usage()
        
        # Improve prompt with a separate try/except to handle specific improvement errors
        try:
            improved = improve_prompt(prompt)
        except Exception as imp_error:
            logger.error(f"Error in prompt improvement: {str(imp_error)}", exc_info=True)
            # Return a friendly error message
            return jsonify({
                'error': 'Prompt improvement failed',
                'message': f"Failed to improve prompt: {str(imp_error)}. Please try with a simpler description."
            }), 500
            
        # Limit response size
        if len(improved) > MAX_PROMPT_LENGTH * 2:
            logger.warning(f"Improved prompt too large ({len(improved)} chars), truncating")
            improved = improved[:MAX_PROMPT_LENGTH * 2] + "\n\nNote: This response was truncated due to size limits."
            
        processing_time = time.time() - start_time
        logger.info(f"Successfully improved prompt in {processing_time:.2f} seconds")
        
        # Memory usage after improvement
        after_mem = log_memory_usage()
        logger.info(f"Memory usage for improvement: {after_mem - before_mem:.2f} MB")
        
        force_gc()  # Clean up memory
        return jsonify({'improved_prompt': improved})
    except TimeoutError as e:
        logger.error(f"Request timed out: {str(e)}")
        force_gc()  # Try to clean up memory
        return jsonify({'error': 'Request timed out'}), 408
    except Exception as e:
        logger.error(f"Error in improve_prompt_route: {str(e)}", exc_info=True)
        logger.error(traceback.format_exc())
        force_gc()  # Try to clean up memory
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    # Include memory and request info in health check
    import psutil
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / (1024 * 1024)
    
    return jsonify({
        'status': 'ok',
        'memory_usage_mb': round(memory_mb, 2),
        'active_requests': active_requests,
        'total_requests': request_count,
        'uptime_seconds': int(time.time() - process.create_time())
    })

@app.route('/stats', methods=['GET'])
def stats():
    # More detailed stats endpoint
    import psutil
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    return jsonify({
        'memory': {
            'rss_mb': round(memory_info.rss / (1024 * 1024), 2),
            'vms_mb': round(memory_info.vms / (1024 * 1024), 2),
            'percent': round(process.memory_percent(), 2)
        },
        'cpu_percent': process.cpu_percent(),
        'threads': len(process.threads()),
        'active_requests': active_requests,
        'total_requests': request_count,
        'uptime_seconds': int(time.time() - process.create_time())
    })

if __name__ == '__main__':
    app.run(port=5000)
