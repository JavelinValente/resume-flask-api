import os
import json
import boto3
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from resume_parser import parse_resume

app = Flask(__name__, static_folder='../frontend', static_url_path='/')

# Validate S3_BUCKET at startup
S3_BUCKET = os.environ.get("RESUME_BUCKET_NAME")
if not S3_BUCKET:
    raise ValueError("RESUME_BUCKET_NAME environment variable is required")

s3_client = boto3.client('s3')

@app.route('/upload', methods=['POST'])
def upload_resume():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    file_path = f"/tmp/{filename}"
    
    try:
        file.save(file_path)
        parsed_data = parse_resume(file_path)
        
        s3_key = f"resumes/{os.path.splitext(filename)[0]}.json"
        s3_client.put_object(
            Bucket=S3_BUCKET, 
            Key=s3_key, 
            Body=json.dumps(parsed_data)
        )
        
        return jsonify({'status': 'success', 's3_key': s3_key})
    
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': f'Failed to process resume: {str(e)}'
        }), 500
    
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

# Serve frontend
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
