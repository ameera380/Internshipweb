from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from markupsafe import escape
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, StudentProfile, CompanyProfile, Internship, CV, Match
import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv 
from werkzeug.utils import secure_filename
import PyPDF2
import docx

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///internship.db'

db.init_app(app)
CORS(app)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
load_dotenv()
DEPT_EMAIL = os.getenv('DEPT_EMAIL')
DEPT_EMAIL_PASSWORD = os.getenv('DEPT_EMAIL_PASSWORD')
SECRET_KEY = os.getenv('SECRET_KEY', 'change-this-for-demo')
serializer = URLSafeTimedSerializer(SECRET_KEY)
BASE_URL = 'http://127.0.0.1:5000'

COMMON_SKILLS = [
    "Python", "Java", "JavaScript", "SQL", "Excel", "PowerPoint",
    "Marketing", "Public Speaking", "Photoshop", "Social Media",
    "Data Analysis", "Machine Learning", "C++", "HTML", "CSS",
    "Project Management", "Communication", "Leadership", "Research",
    "Accounting", "Finance", "Sales", "Customer Service", "Writing",
    "Graphic Design", "Video Editing", "React", "Flask", "Django",
    "Networking", "Teamwork"
]

def extract_text_from_pdf(filepath):
    text = ""
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def extract_text_from_docx(filepath):
    doc = docx.Document(filepath)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_skills(text):
    text_lower = text.lower()
    found_skills = [skill for skill in COMMON_SKILLS if skill.lower() in text_lower]
    return ", ".join(found_skills)

def calculate_match(student, cv, internship):
    required = [s.strip().lower() for s in (internship.required_skills or '').split(',') if s.strip()]
    owned = [s.strip().lower() for s in (cv.skills or '').split(',') if s.strip()]

    matched = [s for s in required if s in owned]
    skills_score = (len(matched) / len(required) * 100) if required else 0
    location_score = 100 if (student.city and student.city == internship.city) else 0

    total = round(0.8 * skills_score + 0.2 * location_score, 2)
    return total, round(skills_score, 2), location_score, matched


def send_email(msg):
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20) as server:
            server.login(DEPT_EMAIL, DEPT_EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Port 465 failed: {e}")
    try:
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=20) as server:
            server.starttls()
            server.login(DEPT_EMAIL, DEPT_EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Port 587 failed: {e}")
    return False


def notify_department(company, internship, student):
    approve_token = serializer.dumps(company.company_id, salt='vet-approve')
    reject_token = serializer.dumps(company.company_id, salt='vet-reject')
    approve_link = f"{BASE_URL}/vet/approve/{approve_token}"
    reject_link = f"{BASE_URL}/vet/reject/{reject_token}"

    body = (
        f"A student has applied to an internship at a company that is not yet vetted by the university.\n\n"
        f"Company: {company.company_name}\n"
        f"Internship: {internship.title}\n"
        f"Student: {student.fullName} ({student.major})\n\n"
        f"APPROVE this company:\n{approve_link}\n\n"
        f"REJECT this company (blacklist):\n{reject_link}\n"
    )
    msg = MIMEText(body)
    msg['Subject'] = f"Vetting Required: {company.company_name}"
    msg['From'] = DEPT_EMAIL
    msg['To'] = DEPT_EMAIL

    if send_email(msg):
        print("Department notified by email.")
    else:
        print("Email failed on both ports.")

def generate_matches(student_id):
    student = StudentProfile.query.get(student_id)
    cv = CV.query.filter_by(student_id=student_id).first()
    if not student or not cv:
        return []

    results = []
    for internship in Internship.query.filter_by(status='open').all():
        if internship.company.is_blacklisted:
            continue  # blocked by the university

        total, skills_score, location_score, matched = calculate_match(student, cv, internship)
        if skills_score == 0:
            continue

        match = Match.query.filter_by(student_id=student_id, internship_id=internship.internship_id).first()
        if match:
            match.match_score = total
        else:
            match = Match(student_id=student_id, internship_id=internship.internship_id,
                          match_score=total, status='recommended')
            db.session.add(match)
        results.append({
            'internship_id': internship.internship_id,
            'title': internship.title,
            'match_score': total,
            'matched_skills': matched,
            'status': match.status
        })

    db.session.commit()
    return results
    
def overall_status(match):
    company = match.internship.company
    if match.status == 'recommended':
        return 'recommended'
    if match.status == 'rejected_by_company':
        return 'rejected_by_company'
    if company.is_blacklisted:
        return 'rejected_by_university'
    if match.status == 'accepted_by_company':
        return 'internship_confirmed' if company.is_vetted else 'accepted_waiting_university'
    return 'applied' if company.is_vetted else 'applied_waiting_university'
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
    internship.duration_months = data.get('duration_months', internship.duration_months)
    internship.work_mode = data.get('work_mode', internship.work_mode)
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

@app.route('/upload-cv', methods=['POST'])
def upload_cv():
    student_id = request.form.get('student_id')
    file = request.files.get('cv_file')

    if not student_id or not file:
        return jsonify({'error': 'Missing student_id or file'}), 400

    student_id = int(student_id)
    student = StudentProfile.query.get(student_id)
    if not student:
        return jsonify({'error': 'Student profile not found'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    if filename.lower().endswith('.pdf'):
        text = extract_text_from_pdf(filepath)
    elif filename.lower().endswith('.docx'):
        text = extract_text_from_docx(filepath)
    else:
        return jsonify({'error': 'Unsupported file type. Please upload PDF or DOCX.'}), 400

    skills = extract_skills(text)

    existing_cv = CV.query.filter_by(student_id=student_id).first()
    if existing_cv:
        existing_cv.skills = skills
        existing_cv.experience = text[:2000]
    else:
        new_cv = CV(
            student_id=student_id,
            skills=skills,
            experience=text[:2000]
        )
        db.session.add(new_cv)

    db.session.commit()

    matches = generate_matches(student_id)

    return jsonify({
        'message': 'CV uploaded and processed successfully',
        'extracted_skills': skills,
        'matches_found': len(matches)
    }), 201
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

@app.route('/generate-matches', methods=['POST'])
def generate_matches_route():
    data = request.get_json()
    student_id = int(data.get('student_id'))
    results = generate_matches(student_id)
    return jsonify(results), 200

@app.route('/matches/<int:student_id>', methods=['GET'])
def get_matches(student_id):
    matches = Match.query.filter_by(student_id=student_id).order_by(Match.match_score.desc()).all()
    return jsonify([{
        'internship_id': m.internship_id,
        'title': m.internship.title,
        'company_name': m.internship.company.company_name,
        'match_score': float(m.match_score),
        'status': overall_status(m)
    } for m in matches]), 200
    
def apply_vetting_decision(company_id, approve):
    company = CompanyProfile.query.get(company_id)
    if not company:
        return None, 0

    company.is_vetted = approve
    company.is_blacklisted = not approve
    db.session.commit()

    affected = Match.query.join(Internship).filter(
        Internship.company_id == company_id,
        Match.status.in_(['applied', 'accepted_by_company'])
    ).count()
    return company, affected


@app.route('/vet/<action>/<token>', methods=['GET'])
def vet_from_email(action, token):
    if action not in ('approve', 'reject'):
        return '<h3>Invalid link.</h3>', 400
    try:
        company_id = serializer.loads(token, salt=f'vet-{action}', max_age=60 * 60 * 24 * 7)
    except SignatureExpired:
        return '<h3>This link has expired.</h3>', 400
    except BadSignature:
        return '<h3>Invalid link.</h3>', 400

    company, count = apply_vetting_decision(company_id, approve=(action == 'approve'))
    if not company:
        return '<h3>Company not found.</h3>', 404

    verb = 'approved' if action == 'approve' else 'rejected'
    return f'<h2>Company "{escape(company.company_name)}" {verb}.</h2><p>{count} application(s) affected.</p>'




@app.route('/apply', methods=['POST'])
def apply_to_internship():
    data = request.get_json()
    student_id = int(data.get('student_id'))
    internship_id = int(data.get('internship_id'))

    match = Match.query.filter_by(student_id=student_id, internship_id=internship_id).first()
    if not match:
        return jsonify({'error': 'No match found for this internship'}), 404
    if match.status != 'recommended':
        return jsonify({'error': f'Cannot apply. Current status: {match.status}'}), 400

    internship = match.internship
    company = internship.company
    if company.is_blacklisted:
        return jsonify({'error': 'This company is not approved by the university'}), 400

    match.status = 'applied'
    db.session.commit()

    if not company.is_vetted:
        already_requested = Match.query.join(Internship).filter(
            Internship.company_id == company.company_id,
            Match.status != 'recommended',
            Match.match_id != match.match_id
        ).first()
        if not already_requested:
            notify_department(company, internship, match.student)

    return jsonify({'message': 'Application sent to the company'}), 200


@app.route('/company-applicants/<int:company_id>', methods=['GET'])
def company_applicants(company_id):
    matches = Match.query.join(Internship).filter(
        Internship.company_id == company_id,
        Match.status != 'recommended'
    ).order_by(Match.match_score.desc()).all()

    result = []
    for m in matches:
        student = m.student
        cv = student.cv
        result.append({
            'match_id': m.match_id,
            'student_name': student.fullName,
            'major': student.major,
            'city': student.city,
            'area': student.area,
            'skills': cv.skills if cv else '',
            'internship_title': m.internship.title,
            'match_score': float(m.match_score),
            'status': overall_status(m),
            'decision_pending': m.status == 'applied'
        })
    return jsonify(result), 200

@app.route('/company-decision', methods=['POST'])
def company_decision():
    data = request.get_json()
    match_id = int(data.get('match_id'))
    decision = data.get('decision')

    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Application not found'}), 404
    if match.status != 'applied':
        return jsonify({'error': f'Already decided. Current status: {match.status}'}), 400
    if decision not in ('accept', 'reject'):
        return jsonify({'error': 'Decision must be accept or reject'}), 400

    match.status = 'accepted_by_company' if decision == 'accept' else 'rejected_by_company'
    db.session.commit()
    return jsonify({'message': f'Application {decision}ed', 'status': overall_status(match)}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)