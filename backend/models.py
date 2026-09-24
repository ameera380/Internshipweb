from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'student' or 'company'

class StudentProfile(db.Model):
    __tablename__ = 'student_profile'
    student_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    fullName = db.Column(db.String(255))
    location = db.Column(db.String(255))
    major = db.Column(db.String(255))

    cv = db.relationship('CV', backref='student', uselist=False)
    matches = db.relationship('Match', backref='student', lazy=True)

class CompanyProfile(db.Model):
    __tablename__ = 'company_profile'
    company_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    company_name = db.Column(db.String(255))
    location = db.Column(db.String(255))

    internships = db.relationship('Internship', backref='company', lazy=True)

class CV(db.Model):
    __tablename__ = 'cv'
    CV_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.student_id'))
    skills = db.Column(db.Text)
    education_extracted = db.Column(db.Text)
    experience = db.Column(db.Text)

class Internship(db.Model):
    __tablename__ = 'internship'
    internship_id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_profile.company_id'))
    title = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255))
    duration = db.Column(db.String(100))
    status = db.Column(db.String(50), default='open')
    required_skills = db.Column(db.Text)

    matches = db.relationship('Match', backref='internship', lazy=True)

class Match(db.Model):
    __tablename__ = 'match'
    match_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profile.student_id'))
    internship_id = db.Column(db.Integer, db.ForeignKey('internship.internship_id'))
    match_score = db.Column(db.Numeric(5, 2))
    status = db.Column(db.String(50), default='pending')