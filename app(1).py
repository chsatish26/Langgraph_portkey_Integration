"""
AWS Bedrock Claude Sonnet 4 Pricing Calculator
Minimal Flask app with text and file support
"""

import os
import io
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Claude Sonnet 4 Pricing
SONNET_4 = {
    'model_id': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
    'name': 'Claude Sonnet 4.5',
    'input_price_per_1k': 0.003,   # $3 per 1M tokens
    'output_price_per_1k': 0.015,  # $15 per 1M tokens
}

REQUESTS_PER_DAY = 100  # Fixed for projections


def estimate_text_tokens(text):
    """Estimate tokens from text (~4 chars = 1 token)"""
    if not text:
        return 0
    return max(1, len(text.strip()) // 4)


def estimate_output_tokens(input_tokens):
    """Estimate output tokens (60% of input, min 50, max 4000)"""
    estimated = int(input_tokens * 0.6)
    return max(50, min(estimated, 4000))


def count_pdf_pages(file_content):
    """Count PDF pages (simple heuristic)"""
    try:
        # Count /Page occurrences
        pages = file_content.count(b'/Page')
        return max(1, pages)
    except:
        return 1


def process_files(files):
    """Process uploaded files and return token counts"""
    text_tokens = 0
    image_tokens = 0
    document_tokens = 0
    
    for file in files:
        filename = secure_filename(file.filename).lower()
        content = file.read()
        
        # Images
        if any(filename.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            image_tokens += 1600
        
        # PDFs
        elif filename.endswith('.pdf'):
            pages = count_pdf_pages(content)
            document_tokens += pages * 500
        
        # Text files
        elif filename.endswith('.txt'):
            try:
                text = content.decode('utf-8')
                text_tokens += estimate_text_tokens(text)
            except:
                text_tokens += len(content) // 4
    
    return {
        'text_tokens': text_tokens,
        'image_tokens': image_tokens,
        'document_tokens': document_tokens
    }


def calculate_cost(input_tokens, output_tokens):
    """Calculate cost"""
    input_cost = (input_tokens / 1000) * SONNET_4['input_price_per_1k']
    output_cost = (output_tokens / 1000) * SONNET_4['output_price_per_1k']
    total_cost = input_cost + output_cost
    
    # Projections (100 requests/day)
    daily_cost = total_cost * REQUESTS_PER_DAY
    weekly_cost = daily_cost * 7
    monthly_cost = daily_cost * 30
    
    return {
        'input': round(input_cost, 6),
        'output': round(output_cost, 6),
        'total_per_request': round(total_cost, 6),
        'weekly_estimate': round(weekly_cost, 4),
        'monthly_estimate': round(monthly_cost, 4)
    }


@app.after_request
def after_request(response):
    """Enable CORS"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST')
    return response


@app.route('/')
def index():
    """Render calculator page"""
    return render_template('index.html')


@app.route('/api/calc', methods=['POST'])
def calculate():
    """Calculate pricing"""
    try:
        breakdown = {'text_tokens': 0, 'image_tokens': 0, 'document_tokens': 0}
        
        # Check if files were uploaded
        if request.files and 'files' in request.files:
            files = request.files.getlist('files')
            # Filter out empty files
            valid_files = [f for f in files if f and f.filename]
            if valid_files:
                breakdown = process_files(valid_files)
        
        # Check for text input (works for both JSON and form data)
        if request.is_json:
            data = request.json
            text_input = data.get('text_input', '')
            if text_input:
                breakdown['text_tokens'] = estimate_text_tokens(text_input)
        elif request.form:
            text_input = request.form.get('text_input', '')
            if text_input:
                breakdown['text_tokens'] = estimate_text_tokens(text_input)
        
        # Calculate totals
        total_input_tokens = (
            breakdown['text_tokens'] + 
            breakdown['image_tokens'] + 
            breakdown['document_tokens']
        )
        
        if total_input_tokens == 0:
            return jsonify({
                'success': False,
                'error': 'Please enter a prompt or upload files'
            }), 400
        
        # Estimate output
        output_tokens = estimate_output_tokens(total_input_tokens)
        
        # Calculate cost
        cost = calculate_cost(total_input_tokens, output_tokens)
        
        return jsonify({
            'success': True,
            'model_id': SONNET_4['model_id'],
            'tokens': {
                'input': total_input_tokens,
                'output': output_tokens,
                'breakdown': breakdown
            },
            'cost': cost,
            'pricing_per_1k': {
                'input': SONNET_4['input_price_per_1k'],
                'output': SONNET_4['output_price_per_1k']
            }
        })
    
    except Exception as e:
        print(f"Error in calculate: {str(e)}")  # Log for debugging
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'model': SONNET_4['name']
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    print("="*60)
    print("CLAUDE SONNET 4 PRICING CALCULATOR")
    print("="*60)
    print(f"Server: http://0.0.0.0:{port}")
    print(f"Model: {SONNET_4['name']}")
    print(f"Debug: {debug}")
    print("="*60)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
