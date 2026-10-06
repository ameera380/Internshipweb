from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, StudentProfile, CompanyProfile, Internship

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
@app.route('/company-profile', methods=['POST'])
def create_company_profile():
    data = request.get_json()
    company_id = int(data.get('company_id'))
    company_name = data.get('company_name')
    city = data.get('city')
    area = data.get('area')

    user = User.query.get(company_id)
    if not user or user.role != 'company':
        return jsonify({'error': 'Invalid company user'}), 400

    profile = CompanyProfile.query.get(company_id)
    if profile:
        return jsonify({'error': 'Profile already exists'}), 400

    new_profile = CompanyProfile(
        company_id=company_id,
        company_name=company_name,
        city=city,
        area=area
    )
    db.session.add(new_profile)
    db.session.commit()

    return jsonify({'message': 'Company profile created successfully'}), 201

@app.route('/internship', methods=['POST'])
def create_internship():
    data = request.get_json()
    company_id = int(data.get('company_id'))
    title = data.get('title')
    city = data.get('city')
    area = data.get('area')
    duration_months = int(data.get('duration_months'))
    work_mode = data.get('work_mode')
    required_skills = data.get('required_skills')

    company = CompanyProfile.query.get(company_id)
    if not company:
        return jsonify({'error': 'Invalid company'}), 400

    new_internship = Internship(
        company_id=company_id,
        title=title,
        city=city,
        area=area,
        duration_months=duration_months,
        work_mode=work_mode,
        required_skills=required_skills,
        status='open'
)
    db.session.add(new_internship)
    db.session.commit()

    return jsonify({'message': 'Internship posted successfully', 'internship_id': new_internship.internship_id}), 201


@app.route('/internship/<int:internship_id>', methods=['PUT'])
def edit_internship(internship_id):
    data = request.get_json()
    internship = Internship.query.get(internship_id)
    if not internship:
        return jsonify({'error': 'Internship not found'}), 404

    internship.title = data.get('title', internship.title)
    internship.city = data.get('city', internship.city)
    internship.area = data.get('area', internship.area)
    internship.duration = data.get('duration', internship.duration)
    internship.required_skills = data.get('required_skills', internship.required_skills)

    db.session.commit()
    return jsonify({'message': 'Internship updated successfully'}), 200


@app.route('/internship/<int:internship_id>/close', methods=['PUT'])
def close_internship(internship_id):
    internship = Internship.query.get(internship_id)
    if not internship:
        return jsonify({'error': 'Internship not found'}), 404

    internship.status = 'closed'
    db.session.commit()
    return jsonify({'message': 'Internship closed successfully'}), 200

@app.route('/internships', methods=['GET'])
def browse_internships():
    city = request.args.get('city')
    area = request.args.get('area')
    work_mode = request.args.get('work_mode')
    duration_months = request.args.get('duration_months')
    skills = request.args.get('skills')

    query = Internship.query.filter_by(status='open')

    if city:
        query = query.filter_by(city=city)
    if area:
        query = query.filter_by(area=area)
    if work_mode:
        query = query.filter_by(work_mode=work_mode)
    if duration_months:
        query = query.filter_by(duration_months=int(duration_months))
    if skills:
        query = query.filter(Internship.required_skills.ilike(f'%{skills}%'))

    results = query.all()

    internships_list = []
    for i in results:
        internships_list.append({
            'internship_id': i.internship_id,
            'title': i.title,
            'city': i.city,
            'area': i.area,
            'work_mode': i.work_mode,
            'duration_months': i.duration_months,
            'required_skills': i.required_skills,
            'company_id': i.company_id
        })

    return jsonify(internships_list), 200
    
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)