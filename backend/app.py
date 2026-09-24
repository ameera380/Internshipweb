from flask import Flask, jsonify
from models import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///internship.db'

db.init_app(app)

@app.route('/')
def home():
    return jsonify({'message': 'Backend is running'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)