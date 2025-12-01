import os
import json
import boto3
import traceback
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from resume_parser import parse_resume

app = Flask(__name__, static_folder='frontend', static_url_path='/')

# Validate S3_BUCKET at startup
S3_BUCKET = os.environ.get("RESUME_BUCKET_NAME")
if not S3_BUCKET:
    raise ValueError("RESUME_BUCKET_NAME environment variable is required")

s3_client = boto3.client('s3')

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_resume():
    temp_file = None
    try:
        # Debug logging
        app.logger.info(f"Upload request received. Files: {request.files}")
        app.logger.info(f"Form data: {request.form}")
        
        if 'file' not in request.files:
            app.logger.error("No file part in request")
            return jsonify({'status': 'error', 'message': 'No file part'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            app.logger.error("Empty filename")
            return jsonify({'status': 'error', 'message': 'No selected file'}), 400
        
        if not allowed_file(file.filename):
            app.logger.error(f"Invalid file type: {file.filename}")
            return jsonify({
                'status': 'error', 
                'message': 'Invalid file type. Only PDF and DOC/DOCX files are allowed'
            }), 400
        
        filename = secure_filename(file.filename)
        
        # Create a temporary file with proper permissions
        # The temp file will be owned by the process (root in this case)
        suffix = os.path.splitext(filename)[1]  # Get file extension
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        file_path = temp_file.name
        temp_file.close()  # Close so we can write to it with Flask
        
        app.logger.info(f"Saving file to: {file_path}")
        file.save(file_path)
        
        app.logger.info(f"Parsing resume: {filename}")
        try:
            parsed_data = parse_resume(file_path)
        except Exception as parse_error:
            app.logger.error(f"Failed to parse resume: {str(parse_error)}")
            # Return a more user-friendly error
            return jsonify({
                'status': 'error',
                'message': f'Failed to parse resume. Please ensure the file is a valid PDF or DOCX document.'
            }), 400
        
        s3_key = f"resumes/{os.path.splitext(filename)[0]}.json"
        app.logger.info(f"Uploading to S3: {S3_BUCKET}/{s3_key}")
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(parsed_data),
            ContentType='application/json'
        )
        
        app.logger.info(f"Upload successful: {s3_key}")
        return jsonify({
            'status': 'success', 
            's3_key': s3_key,
            'parsed_data': parsed_data
        })
        
    except Exception as e:
        app.logger.error(f"Error processing resume: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f'Failed to process resume: {str(e)}'
        }), 500
        
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(file_path):
            try:
                os.remove(file_path)
                app.logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                app.logger.error(f"Failed to remove temp file: {e}")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'bucket': S3_BUCKET,
        'environment': 'production'
    })

@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(os.path.join('frontend', path)):
        return send_from_directory('frontend', path)
    return send_from_directory('frontend', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
