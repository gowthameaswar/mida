from flask import Flask, request, jsonify
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from pymongo import MongoClient
import os
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# MongoDB connection
mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://gowthambalaji344:gowthambalaji344@mida.2osc8bi.mongodb.net/')
client = MongoClient(mongo_uri)
db = client.hospitalDB

# Check MongoDB connection
try:
    client.admin.command('ping')
    print("Connected to MongoDB successfully")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

@app.route('/api/hospital/register', methods=['POST'])
def register_hospital():
    data = request.json
    try:
        hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
        hospital_id = str(uuid.uuid4())  # Generate UUID

        hospital = {
            'id': hospital_id,
            'name': data['hospitalName'],
            'location': data['location'],
            'staffSize': data['staffSize'],
            'adminEmail': data['adminEmail'],
            'password': hashed_password
        }
        result = db.hospitals.insert_one(hospital)
        hospital['_id'] = str(result.inserted_id)
        return jsonify(hospital)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_type = data.get('userType')
    email = data.get('email')
    password = data.get('password')

    try:
        if user_type == 'admin':
            user = db.hospitals.find_one({'adminEmail': email})
        elif user_type == 'staff':
            user = db.staff.find_one({'email': email})
        else:
            return jsonify({'error': 'Invalid user type'}), 400

        if not user or not bcrypt.check_password_hash(user['password'], password):
            return jsonify({'error': 'Invalid credentials'}), 401

        # Store user UUID and email in online users collection
        db.online_users.insert_one({
            'id': user['id'],
            'email': email,
            'userType': user_type
        })

        return jsonify({'message': f'{user_type.capitalize()} login successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/profile', methods=['GET'])
def get_admin_profile():
    try:
        # Fetch the logged-in user's ID from the online_users collection
        online_user = db.online_users.find_one()
        if not online_user:
            return jsonify({'error': 'No user is logged in'}), 401

        user_id = online_user['id']
        user = db.hospitals.find_one({'id': user_id})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Return the user's profile details
        profile = {
            'hospitalId': user['id'],
            'name': user['name'],
            'location': user['location'],
            'staffSize': user['staffSize'],
            'adminEmail': user['adminEmail']
        }

        return jsonify(profile)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    try:
        # Clear all data in online_users collection
        db.online_users.delete_many({})
        return jsonify({'message': 'Logged out successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/admin/add-staff', methods=['POST'])
def add_staff():
    data = request.json
    try:
        # Generate a UUID for the staff member
        staff_id = str(uuid.uuid4())

        # Fetch the current online user to get their hospital ID
        online_user = db.online_users.find_one()
        if not online_user:
            return jsonify({'error': 'No user is logged in'}), 401

        # Fetch the hospital details
        hospital = db.hospitals.find_one({'id': online_user['id']})
        if not hospital:
            return jsonify({'error': 'Hospital not found'}), 404

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')

        # Create the staff member record
        staff = {
            'id': staff_id,
            'name': data['staffName'],
            'email': data['email'],
            'password': hashed_password,
            'role': data['role'],
            'hospitalId': online_user['id']
        }
        result = db.staff.insert_one(staff)
        staff['_id'] = str(result.inserted_id)

        # Send email to staff member
        send_email(data['email'], data['staffName'], data['password'], hospital['name'])

        return jsonify(staff)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
def send_email(to_email, staff_name, password, hospital_name):
    try:
        # Email configuration
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = "gowthambalaji344@gmail.com"  # Your Gmail address
        smtp_password = ""  # Your App Password

        # Email content
        subject = "Your Staff Account Details"
        body = f"""
        Hi {staff_name},

        Your account has been created on the Medical Imaging Diagnostic Assistant. Here are your login details:

        Email: {to_email}
        Password: {password}
        
        Hospital: {hospital_name}

        Please log in and change your password as soon as possible.

        Happy reporting!

        Regards,
        {hospital_name} Admin
        """

        # Setting up the MIME
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connecting to the server and sending the email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        text = msg.as_string()
        server.sendmail(smtp_user, to_email, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")


@app.route('/api/admin/staff', methods=['GET'])
def get_staff():
    try:
        # Fetch the logged-in user's ID from the online_users collection
        online_user = db.online_users.find_one()
        if not online_user:
            return jsonify({'error': 'No user is logged in'}), 401

        hospital_id = online_user['id']
        staff_members = list(db.staff.find({'hospitalId': hospital_id}))
        
        for staff in staff_members:
            staff['_id'] = str(staff['_id'])

        return jsonify(staff_members)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/delete-staff/<string:id>', methods=['DELETE'])
def delete_staff(id):
    try:
        result = db.staff.delete_one({'id': id})
        if result.deleted_count == 1:
            return jsonify({'message': 'Staff deleted successfully'})
        else:
            return jsonify({'error': 'Staff not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
