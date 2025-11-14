print("System starting...")
import os
from flask import Flask, request, render_template, send_file, jsonify
import pandas as pd
from fpdf import FPDF
import io
import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# --- 1. LOAD ENVIRONMENT VARIABLES & CONFIGURE GEMINI ---
load_dotenv() 
API_KEY = os.getenv("GEMINI_API_KEY") 

# Define the bot's system instruction
SYSTEM_INSTRUCTION = (
    "You are a helpful university admissions assistant for the University of Ibadan (UI). "
    "Your main job is to answer questions about courses, faculties, and admission requirements at UI. "
    "Do not answer questions that are not related to academics or university life. "
    "Keep your answers helpful and concise."
)


# --- ADD THIS DEBUG LINE ---
print(f"DEBUG: Is API Key loaded? {API_KEY is not None}")
# ---------------------------
try:
    # Configure the Gemini API
    genai.configure(api_key=API_KEY)
    # Pass system_instruction at creation time
    model = genai.GenerativeModel(
        'gemini-1.5-flash-latest',
        system_instruction=SYSTEM_INSTRUCTION
    )
    print("Gemini model loaded successfully.")
except Exception as e:
    print(f"CRITICAL ERROR: Could not configure Gemini. {e}")
    model = None
# ----------------------------------------------------

# This line creates 'app'
app = Flask(__name__) 

# Now this line can use 'app' without an error
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "default_secret_key")

# --- 2. DATABASE LOADING ---
try:
    COURSE_DATA = pd.read_csv('courses.csv')
    COURSE_DATA['required_subjects'] = COURSE_DATA['required_subjects'].astype(str)
    print(f"Database loaded successfully: {len(COURSE_DATA)} courses found.")
except FileNotFoundError:
    print("CRITICAL ERROR: courses.csv not found.")
    COURSE_DATA = pd.DataFrame()

# --- 3. CORE RECOMMENDATION ENGINE ---
def recommend_courses(jamb_score, preferred_subject, preferred_faculty):
    """
    Filters the main COURSE_DATA DataFrame based on user's criteria.
    """
    if COURSE_DATA.empty:
        return pd.DataFrame(), 'none' # 'none' = database error

    df = COURSE_DATA.copy()

    # Apply base filters that are always required
    mask_score = df['min_jamb'] <= jamb_score
    mask_subject = df['required_subjects'].str.contains(preferred_subject, case=False, na=False)

    # --- THIS IS THE FIX ---
    # Only apply the faculty filter if the user selected a specific faculty
    if preferred_faculty.lower() != 'all':
        mask_faculty = df['faculty'].str.lower() == preferred_faculty.lower()
        combined_mask = mask_score & mask_subject & mask_faculty
    else:
        # If "All Faculties" is chosen, don't filter by faculty
        combined_mask = mask_score & mask_subject
    # ----------------------

    results_df = df[combined_mask]

    # Sort by JAMB score, descending
    results_df = results_df.sort_values(by='min_jamb', ascending=False)

    status = 'found' if not results_df.empty else 'not_found'

    return results_df, status
    status = 'found' if not results_df.empty else 'not_found'
    
    return results_df, status

# --- 4. PDF GENERATION ---
class PDF(FPDF):
    """Custom PDF class to create header and footer."""
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'UI Course Recommendation Slip', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, f'Generated: {datetime.date.today().strftime("%Y-%m-%d")}', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_slip(df_results, jamb, subject, faculty):
    """
    Generates a PDF slip from the recommendation results and returns it as bytes.
    """
    pdf = PDF()
    pdf.add_page()
    
    # User Info Section
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Your Admission Profile', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f'  JAMB Score: {jamb}', 0, 1)
    pdf.cell(0, 8, f'  Preferred Faculty: {faculty}', 0, 1)
    pdf.cell(0, 8, f'  Core Subject: {subject}', 0, 1)
    pdf.ln(10)
    
    # Results Section
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Recommended Courses', 0, 1)
    pdf.set_font('Arial', '', 10)
    
    if df_results.empty:
        pdf.cell(0, 10, 'No courses found matching your criteria.', 0, 1)
    else:
        for index, row in df_results.iterrows():
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 8, f"{row['course_name']} (Cut-off: {row['min_jamb']})", 0, 1)
            pdf.set_font('Arial', '', 9)
            pdf.multi_cell(0, 5, f"  Faculty: {row['faculty']}\n  Duration: {row['duration']}\n  Careers: {row['careers']}\n")
            pdf.ln(3)

    # Return as bytes
    return pdf.output(dest='S').encode('latin-1')

# --- 5. GEMINI HELPER FUNCTION ---
def get_gemini_response(user_message):
    """
    Generates a response from the Gemini API with specific context.
    """
    if model is None:
        return "Sorry, the AI model is not available. Please check server logs."
    try:
        # We just send the user message directly.
        # The system_instruction is already set in the model.
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "I'm having trouble connecting to my brain right now. Please try again."

# --- 6. FLASK ROUTES ---
@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles the main page and the recommendation form submission."""
    faculties = sorted(COURSE_DATA['faculty'].unique()) if not COURSE_DATA.empty else []
    results = None
    search_status = 'pending' # 'pending', 'found', 'not_found', 'none'

    if request.method == 'POST':
        try:
            jamb = int(request.form['jamb'])
            subject = request.form['subject']
            faculty = request.form['faculty']
            
            df_results, search_status = recommend_courses(jamb, subject, faculty)
            results = df_results.to_dict(orient='records')
        
        except ValueError:
            results = []
            # --- THIS IS THE FIX ---
            # Changed 'none' to 'not_found' so the frontend shows a message
            search_status = 'not_found' 
            # ----------------------
        except Exception as e:
            print(f"Search Error: {e}")
            results = []
            search_status = 'not_found'

    return render_template('index.html', results=results, faculties=faculties, status=search_status)

@app.route('/download', methods=['POST'])
def download():
    """Handles the PDF download request."""
    try:
        jamb = int(request.form['jamb'])
        subject = request.form['subject']
        faculty = request.form['faculty']
        
        df_results, _ = recommend_courses(jamb, subject, faculty)
        pdf_bytes = generate_pdf_slip(df_results, jamb, subject, faculty)
        
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'ui_recommendation_slip_{jamb}.pdf'
        )
    except Exception as e:
        print(f"PDF Error: {e}")
        return "Error generating PDF."

@app.route('/chat', methods=['POST'])
def chat():
    """Handles the chatbot API requests."""
    try:
        user_message = request.json.get("message")
        if not user_message:
            return jsonify({"reply": "Please say something!"})
        
        # This now calls the function we defined above
        bot_reply = get_gemini_response(user_message) 
        
        return jsonify({"reply": bot_reply})
    except Exception as e:
        print(f"Chat Error: {e}")
        return jsonify({"reply": "Sorry, the server ran into an internal error."}), 500

# --- 7. RUN THE APP ---
if __name__ == '__main__':
    # Set debug=False for production
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))