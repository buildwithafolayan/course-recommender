print("System starting...")
from flask import Flask, request, render_template
import pandas as pd

app = Flask(__name__)

def load_data():
    return pd.read_csv('courses.csv')

def recommend_courses(jamb_score, preferred_subject):
    df = load_data()
    # Filter Logic
    qualified = df[
        (df['min_jamb'] <= jamb_score) & 
        (df['required_subjects'].str.contains(preferred_subject, case=False))
    ]
    
    if qualified.empty:
        return "<div class='alert alert-warning'>No courses found matching your criteria.</div>"
    
    # Convert to a nice HTML table with Bootstrap classes
    return qualified.to_html(classes='table table-striped table-hover', index=False)

@app.route('/', methods=['GET', 'POST'])
def home():
    results = None
    
    # If the user clicked the "Find My Course" button (POST request)
    if request.method == 'POST':
        # Get data from the form inputs
        user_jamb = int(request.form['jamb'])
        user_subject = request.form['subject']
        
        # Run the logic
        results = recommend_courses(user_jamb, user_subject)

    # Show the page (with results if we have them)
    return render_template('index.html', results=results)

if __name__ == '__main__':
    app.run(debug=True)