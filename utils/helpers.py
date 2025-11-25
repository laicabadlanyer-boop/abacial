import mimetypes
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per requirements


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def scan_file_for_viruses(file_path: str) -> bool:
    """Placeholder virus scanner. Integrate with a real scanner in production."""
    # TODO: Wire up ClamAV or a commercial virus scanning service in production.
    return True


def save_uploaded_file(file, applicant_id):
    if not file or not file.filename:
        return None, 'No file provided.'

    original_filename = secure_filename(file.filename)
    if not allowed_file(original_filename):
        return None, 'Unsupported file type. Please upload a PDF file.'

    file.stream.seek(0, os.SEEK_END)
    file_size = file.stream.tell()
    file.stream.seek(0)

    if file_size > MAX_FILE_SIZE:
        return None, 'File exceeds the 5MB size limit.'

    file_ext = original_filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{applicant_id}_{uuid.uuid4().hex}.{file_ext}"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)

    if not scan_file_for_viruses(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
        return None, 'The uploaded file did not pass the security scan.'

    relative_path = os.path.join(upload_folder, unique_filename).replace('\\', '/')
    mimetype = file.mimetype or mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'

    return (
        {
            'original_filename': original_filename,
            'stored_filename': unique_filename,
            'storage_path': relative_path,
            'file_size': file_size,
            'mime_type': mimetype,
        },
        None,
    )
