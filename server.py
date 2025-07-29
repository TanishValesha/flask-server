import os
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import pandas as pd
from flask_cors import CORS # Import CORS

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed extensions for CSV files
ALLOWED_EXTENSIONS = {'csv'}

# Default Nifty data file
DEFAULT_NIFTY_FILE = 'NIFTY__1D__.csv'

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Renders a simple HTML form for file upload."""
    return render_template_string('''
    <!doctype html>
    <title>Upload Nifty Data</title>
    <h1 style="color: #e2e8f0;">Upload Nifty Candlestick Data (CSV)</h1>
    <form method=post enctype=multipart/form-data action="/upload">
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    <h2 style="color: #e2e8f0;">Uploaded Files:</h2>
    <ul id="fileList" style="color: #a0aec0;"></ul>

    <script>
        // Function to fetch and display uploaded files
        async function fetchFiles() {
            try {
                const response = await fetch('/files');
                const files = await response.json();
                const fileList = document.getElementById('fileList');
                fileList.innerHTML = ''; // Clear existing list
                files.forEach(file => {
                    const li = document.createElement('li');
                    li.textContent = file;
                    fileList.appendChild(li);
                });
            } catch (error) {
                console.error("Error fetching file list:", error);
                const fileList = document.getElementById('fileList');
                fileList.innerHTML = '<li style="color: red;">Could not fetch file list. Is the server running?</li>';
            }
        }

        // Fetch files on page load
        document.addEventListener('DOMContentLoaded', fetchFiles);
    </script>
    ''')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles file uploads."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({"message": f"File {filename} uploaded successfully!"}), 200
    else:
        return jsonify({"error": "Allowed file types are CSV"}), 400

@app.route('/files')
def list_files():
    """Lists all uploaded CSV files."""
    files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if allowed_file(f)]
    return jsonify(files)

@app.route('/data/')
@app.route('/data/<filename>')
def get_data(filename=None):
    """
    Serves data from an uploaded CSV file.
    Uses 'NIFTY__1D__.csv' as default if no filename is provided.
    Assumes CSV has columns: datetime, open, high, low, close
    datetime format: DD/MM/YY HH:MM (e.g., 25/04/05 9:15)
    """
    if filename is None:
        filename = DEFAULT_NIFTY_FILE

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    if not os.path.exists(filepath):
        return jsonify({"error": f"File '{filename}' not found. Please upload it first."}), 404

    try:
        df = pd.read_csv(filepath)

        # Ensure column names are consistent (case-insensitive and handle specific names)
        # Map user's column names to standard names for processing
        column_mapping = {
            'datetime': 'Datetime',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'date': 'Datetime' # In case 'date' is used instead of 'datetime'
        }
        
        # Normalize column names to lowercase for easier matching
        df.columns = [col.lower() for col in df.columns]

        # Rename columns based on mapping
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        required_cols = ['Datetime', 'Open', 'High', 'Low', 'Close']
        if not all(col in df.columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in df.columns]
            return jsonify({"error": f"CSV must contain '{', '.join(missing_cols)}' columns. Found: {list(df.columns)}"}), 400

        # Convert Datetime to timestamp for ApexCharts
        # Use infer_datetime_format=True for better parsing of varied formats
        df['Datetime'] = pd.to_datetime(df['Datetime'], infer_datetime_format=True)
        # ApexCharts expects milliseconds timestamp
        df['Datetime'] = df['Datetime'].apply(lambda x: x.timestamp() * 1000)

        # Sort data by datetime to ensure correct plotting order
        df = df.sort_values(by='Datetime').reset_index(drop=True)

        # Format data for ApexCharts candlestick series
        chart_data = []
        for index, row in df.iterrows():
            chart_data.append({
                'x': int(row['Datetime']),
                'y': [
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close'])
                ]
            })
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({"error": f"Error processing CSV: {str(e)}"}), 500

if __name__ == '__main__':
    # For development, run on a specific port.
    # In a production environment, use a WSGI server like Gunicorn.
    app.run(debug=True, port=5000)
