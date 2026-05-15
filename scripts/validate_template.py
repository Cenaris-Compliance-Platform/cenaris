import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
app = create_app('testing')
with app.app_context():
    tmpl = app.jinja_env.get_or_select_template('main/dashboard.html')
    print('template ok:', tmpl.name)
