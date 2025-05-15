from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from llm_generator import generate_manim_code, improve_prompt
import logging
import gc
import time
import threading
import signal
import os
from functools import wraps

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s [%(levelname)s] %(message)s',
                   handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Configure timeout for hanging requests
TIMEOUT_SECONDS = 180

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

@app.after_request
def after_request(response):
    global active_requests
    active_requests -= 1
    logger.info(f"Request completed. Active requests: {active_requests}")
    gc.collect()  # Force garbage collection after each request
    return response

@app.route('/generate', methods=['POST'])
@timeout_decorator(TIMEOUT_SECONDS)
def generate():
    start_time = time.time()
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
        processing_time = time.time() - start_time
        logger.info(f"Successfully generated code in {processing_time:.2f} seconds")
        
        gc.collect()  # Clean up memory
        return jsonify({'code': code})
    except TimeoutError as e:
        logger.error(f"Request timed out: {str(e)}")
        gc.collect()  # Try to clean up memory
        return jsonify({'error': 'Request timed out', 'code': '// Error: The request took too long to process. Please try with a simpler prompt.'}), 408
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}", exc_info=True)
        gc.collect()  # Try to clean up memory
        return jsonify({'error': str(e), 'code': f"// Error generating code: {str(e)}"}), 500


@app.route('/improve_prompt', methods=['POST'])
@timeout_decorator(TIMEOUT_SECONDS)
def improve_prompt_route():
    start_time = time.time()
    try:
        logger.info(f"Received improve_prompt request from origin: {request.headers.get('Origin', 'Unknown')}")
        
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
        processing_time = time.time() - start_time
        logger.info(f"Successfully improved prompt in {processing_time:.2f} seconds")
        
        gc.collect()  # Clean up memory
        return jsonify({'improved_prompt': improved})
    except TimeoutError as e:
        logger.error(f"Request timed out: {str(e)}")
        gc.collect()  # Try to clean up memory
        return jsonify({'error': 'Request timed out'}), 408
    except Exception as e:
        logger.error(f"Error in improve_prompt_route: {str(e)}", exc_info=True)
        gc.collect()  # Try to clean up memory
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
        'total_requests': request_count
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
        },
        'cpu_percent': process.cpu_percent(),
        'threads': len(process.threads()),
        'active_requests': active_requests,
        'total_requests': request_count
    })

if __name__ == '__main__':
    app.run(port=5000)