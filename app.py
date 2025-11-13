print('System starting...')
from flask import Flask, request, render_template
import pandas as pd
import time 

app = Flask(__name__)

def load_data():
    return pd.read_csv('courses.csv')

def recommend_courses(jamb_score, preferred_subject, preferred_faculty):
    df = load_data()
    
    qualified = df[
        (df['min_jamb'] <= jamb_score) & 
        (df['required_subjects'].str.contains(preferred_subject, case=False))
    ]
    
    if preferred_faculty != "All":
        qualified = qualified[qualified['faculty'] == preferred_faculty]
    
    if qualified.empty:
        return []
    
    return qualified.to_dict(orient='records')

@app.route('/', methods=['GET', 'POST'])
def home():
    results = None
    df = load_data()
    faculties = sorted(df['faculty'].unique())
    
    if request.method == 'POST':
        time.sleep(1.5) 
        
        try:
            user_jamb = int(request.form['jamb'])
            user_subject = request.form['subject']
            user_faculty = request.form['faculty']
            
            results = recommend_courses(user_jamb, user_subject, user_faculty)
        except ValueError:
            results = []

    return render_template('index.html', results=results, faculties=faculties)

if __name__ == '__main__':
    app.run(debug=True)