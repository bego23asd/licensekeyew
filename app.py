from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import uuid
from datetime import datetime, timedelta
from flask import jsonify

app = Flask(__name__)

# Use a local SQLite database named 'database.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define the LicenseKey model
class LicenseKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(20), unique=True, nullable=False)
    expiration_minutes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_logged_in = db.Column(db.Boolean, default=False)
    device_id = db.Column(db.String(50))

# Create the database tables if they don't exist
with app.app_context():
    db.create_all()

# Helper function to generate a random key
def generate_license_key():
    return uuid.uuid4().hex[:12].upper()  # Example: "A1B2C3D4E5F6"

@app.route('/validate-key', methods=['POST'])
def validate_key():
    data = request.get_json()
    license_key = data.get('key')
    device_id = data.get('deviceId')

    if not license_key:
        return jsonify({"status": "error", "message": "No key provided"}), 400

    license = LicenseKey.query.filter_by(key=license_key).first()

    if not license:
        return jsonify({"status": "error", "message": "Invalid key Or Deleted Licensed Key"}), 403

    # Check if key is expired
    expiration_time = license.created_at + timedelta(minutes=license.expiration_minutes)
    if datetime.utcnow() > expiration_time:
        return jsonify({"status": "error", "message": "Key expired"}), 403

    # Check for session conflict
    if license.is_logged_in and license.device_id != device_id:
        return jsonify({"status": "error", "message": "This license is already logged in on another device."}), 403

    # Mark as logged in for this session
    license.is_logged_in = True
    license.device_id = device_id  # Track the device ID
    db.session.commit()

    # Send expiry time in response
    return jsonify({
        "status": "success",
        "message": "Key valid",
        "expiry": expiration_time.isoformat() + "Z"  # Send in ISO format for JS parsing
    }), 200

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    now = datetime.utcnow()
    licenses = LicenseKey.query.all()
    # Pass 'timedelta' into the template so we can use it in Jinja
    return render_template('admin.html', licenses=licenses, now=now, timedelta=timedelta)

@app.route('/generate-key', methods=['POST'])
def generate_key():
    # Grab the 'duration' from the form data
    duration_option = request.form.get("duration", "2_minutes")

    # Map duration options to minutes
    duration_map = {
        "2_minutes": 2,
        "2_hours": 120,
        "1_day": 1440
    }

    if duration_option not in duration_map:
        return "Invalid duration option", 400

    expiration_minutes = duration_map[duration_option]
    key = generate_license_key()

    # Create a new LicenseKey record
    new_license = LicenseKey(key=key, expiration_minutes=expiration_minutes)
    db.session.add(new_license)
    db.session.commit()

    # Redirect back to admin page
    return redirect(url_for('admin_page'))

@app.route('/delete_key/<int:key_id>', methods=['POST'])
def delete_key(key_id):
    # Delete the specified license key
    license_to_delete = LicenseKey.query.get(key_id)
    if license_to_delete:
        db.session.delete(license_to_delete)
        db.session.commit()

    # Redirect back to admin page
    return redirect(url_for('admin_page'))

if __name__ == '__main__':
    app.run(debug=True)
