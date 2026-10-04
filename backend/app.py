from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, StudentProfile

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///internship.db'

db.init_app(app)
CORS(app)

@app.route('/')
def home():
    return jsonify({'message': 'Backend is running'})

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')

    if not email or not password or not role:
        return jsonify({'error': 'Missing email, password, or role'}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'Email already registered'}), 400

    hashed_password = generate_password_hash(password)
    new_user = User(email=email, password=hashed_password, role=role)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid email or password'}), 401

    return jsonify({'message': 'Login successful', 'role': user.role, 'user_id': user.user_id}), 200
@app.route('/student-profile', methods=['POST'])
def create_student_profile():
    data = request.get_json()
    student_id = int(data.get('student_id'))
    fullName = data.get('fullName')
    city = data.get('city')
    area = data.get('area')
    major = data.get('major')

    user = User.query.get(student_id)
    if not user or user.role != 'student':
        return jsonify({'error': 'Invalid student user'}), 400

    profile = StudentProfile.query.get(student_id)
    if profile:
        return jsonify({'error': 'Profile already exists'}), 400

    new_profile = StudentProfile(
        student_id=student_id,
        fullName=fullName,
        city=city,
        area=area,
        major=major
    )
    db.session.add(new_profile)
    db.session.commit()

    return jsonify({'message': 'Student profile created successfully'}), 201

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)