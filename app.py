print('System starting...')
from flask import Flask, request, render_template, send_file
import pandas as pd
from fpdf import FPDF
import io
import datetime

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
    
    return qualified

def generate_pdf_slip(results, jamb, subject):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="University of Ibadan", ln=True, align='C')
    pdf.set_font("Arial", 'I', 12)
    pdf.cell(200, 10, txt="Course Recommendation Slip", ln=True, align='C')
    pdf.line(10, 30, 200, 30) # Draw a line
    pdf.ln(10)

    pdf.set_font("Arial", '', 12)
    pdf.cell(200, 10, txt=f"Date: {datetime.date.today()}", ln=True)
    pdf.cell(200, 10, txt=f"JAMB Score: {jamb}", ln=True)
    pdf.cell(200, 10, txt=f"Subject Strength: {subject}", ln=True)
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(90, 10, txt="Course Name", border=1)
    pdf.cell(60, 10, txt="Faculty", border=1)
    pdf.cell(40, 10, txt="Duration", border=1)
    pdf.ln()

    pdf.set_font("Arial", '', 11)
    for index, row in results.iterrows():
        pdf.cell(90, 10, txt=row['course_name'], border=1)
        pdf.cell(60, 10, txt=row['faculty'], border=1)
        pdf.cell(40, 10, txt=row['duration'], border=1)
        pdf.ln()

    pdf.ln(20)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(200, 10, txt="This is a project work. No signature required.", align='C')

    return pdf.output(dest='S').encode('latin-1')

@app.route('/', methods=['GET', 'POST'])
def home():
    results = None
    faculties = sorted(load_data()['faculty'].unique())
    
    if request.method == 'POST':
        try:
            user_jamb = int(request.form['jamb'])
            user_subject = request.form['subject']
            user_faculty = request.form['faculty']
            
            df_results = recommend_courses(user_jamb, user_subject, user_faculty)
            
            if not df_results.empty:
                results = df_results.to_dict(orient='records')
            else:
                results = []
                
        except ValueError:
            results = []

    return render_template('index.html', results=results, faculties=faculties)

@app.route('/download', methods=['POST'])
def download():
    jamb = int(request.form['jamb'])
    subject = request.form['subject']
    faculty = request.form['faculty']
    
    df_results = recommend_courses(jamb, subject, faculty)
    
    pdf_bytes = generate_pdf_slip(df_results, jamb, subject)
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='ui_admission_slip.pdf'
    )

if __name__ == '__main__':
    app.run(debug=True)