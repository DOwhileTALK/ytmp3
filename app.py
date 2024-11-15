import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import yt_dlp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()  # Necessary for Flask-SocketIO sessions
socketio = SocketIO(app)

# Define output directory for downloaded files
OUTPUT_DIR = os.path.abspath('downloads')
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_info', methods=['POST'])
def get_video_info():
    video_url = request.form['url']
    with yt_dlp.YoutubeDL({'format': 'best'}) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        return jsonify({
            'title': info_dict.get('title'),
            'thumbnail': info_dict.get('thumbnail'),
            'description': info_dict.get('description', 'No description available.'),
            'format': 'mp4' if 'video' in info_dict.get('format', '') else 'mp3'
        })

@socketio.on('download')
def handle_download(data):
    video_url = data['url']
    format_type = data['format']

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if format_type == 'mp4' else 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }] if format_type == 'mp4' else [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'progress_hooks': [lambda d: emit('progress', {
            'status': d['status'],
            'downloaded_bytes': d.get('downloaded_bytes', 0),
            'total_bytes': d.get('total_bytes', 1)
        })],
        'outtmpl': os.path.join(OUTPUT_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            file_name = ydl.prepare_filename(info_dict)
            file_name = file_name.replace('.webm', '.mp3') if format_type == 'mp3' else file_name
            emit('completed', {'file_path': file_name})
    except Exception as e:
        emit('error', {'error': str(e)})

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
