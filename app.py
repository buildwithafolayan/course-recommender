import os
from flask import Flask, request, render_template, send_file, jsonify
import pandas as pd
from fpdf import FPDF
import io
import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import traceback

# Load environment variables from .env file (for local development)
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_INSTRUCTION = (
    "You are a helpful university admissions assistant for the University of Ibadan (UI). "
    "Your main job is to answer questions about courses, faculties, and admission requirements at UI. "
    "Do not answer questions that are not related to academics or university life. "
    "Keep your answers helpful and concise."
)

# --- GEMINI API Configuration and Model Loading ---
# Added extensive logging for debugging, especially in production
print(f"DEBUG: Initial check - Is API Key loaded? {API_KEY is not None}. Length of key: {len(API_KEY) if API_KEY else 0}")
if not API_KEY:
    print("CRITICAL: GEMINI_API_KEY is not loaded from .env or environment variables. Please check your config.")

model = None
try:
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY not found or is empty in environment variables.")

    genai.configure(
        api_key=API_KEY,
        client_options={"api_endpoint": "generativelanguage.googleapis.com"}
    )
    print(f"DEBUG: Gemini API configured successfully with key length {len(API_KEY)}.")

    MODEL_NAME = 'gemini-2.5-flash'

    model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    print(f"DEBUG: Gemini model '{MODEL_NAME}' loaded successfully.")
except ValueError as e:
    print(f"CRITICAL ERROR: Configuration failed for Gemini API - {e}")
    traceback.print_exc() # Print full traceback for ValueErrors during startup
except Exception as e:
    print(f"CRITICAL ERROR: Could not configure Gemini API or load model - {e}")
    traceback.print_exc() # Print full traceback for other exceptions during startup

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "default_secret_key")

# --- Course Data Loading ---
try:
    COURSE_DATA = pd.read_csv('courses.csv')
    COURSE_DATA['required_subjects'] = COURSE_DATA['required_subjects'].astype(str)
    print(f"DEBUG: Course database loaded successfully: {len(COURSE_DATA)} courses found.")
except FileNotFoundError:
    print("CRITICAL ERROR: courses.csv not found. Please ensure it's in the same directory as app.py.")
    COURSE_DATA = pd.DataFrame() # Ensure COURSE_DATA is a DataFrame even on error
except Exception as e:
    print(f"CRITICAL ERROR: Failed to load courses.csv. {e}")
    traceback.print_exc()
    COURSE_DATA = pd.DataFrame() # Ensure COURSE_DATA is a DataFrame even on error

# --- Recommendation Logic ---
def recommend_courses(jamb_score, preferred_subject, preferred_faculty):
    """
    Filters the main COURSE_DATA DataFrame based on user's criteria.
    Returns the results DataFrame and a status string ('found', 'alternative', 'not_found').
    """
    if COURSE_DATA.empty:
        print("DEBUG: COURSE_DATA is empty in recommend_courses function.")
        return pd.DataFrame(), 'not_found' # If no data, nothing can be found

    df = COURSE_DATA.copy()

    # Filter by JAMB score
    mask_score = df['min_jamb'] <= jamb_score

    # Filter by preferred subject (case-insensitive)
    # Ensure preferred_subject is treated as a string for contains()
    mask_subject = df['required_subjects'].astype(str).str.contains(preferred_subject, case=False, na=False)

    # Filter by faculty if 'All' is not selected
    if preferred_faculty.lower() != 'all':
        mask_faculty = df['faculty'].astype(str).str.lower() == preferred_faculty.lower()
        combined_mask = mask_score & mask_subject & mask_faculty
    else:
        combined_mask = mask_score & mask_subject

    results_df = df[combined_mask]

    if results_df.empty:
        # If no exact match, try to find courses based *only* on JAMB score
        alternative_mask = df['min_jamb'] <= jamb_score
        alternative_df = df[alternative_mask].sort_values(by='min_jamb', ascending=False)
        if not alternative_df.empty:
            print(f"DEBUG: Found {len(alternative_df)} alternative courses for JAMB {jamb_score}.")
            return alternative_df, 'alternative'
        else:
            print(f"DEBUG: No courses found for JAMB {jamb_score} even with alternative search.")
            return pd.DataFrame(), 'not_found'

    results_df = results_df.sort_values(by='min_jamb', ascending=False)
    print(f"DEBUG: Found {len(results_df)} exact match courses for JAMB {jamb_score}, subject {preferred_subject}, faculty {preferred_faculty}.")
    status = 'found'

    return results_df, status

# --- PDF Generation ---
class PDF(FPDF):
    """Custom PDF class to create header and footer for the recommendation slip."""
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

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Your Admission Profile', 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f'  JAMB Score: {jamb}', 0, 1)
    pdf.cell(0, 8, f'  Preferred Faculty: {faculty}', 0, 1)
    pdf.cell(0, 8, f'  Core Subject: {subject}', 0, 1)
    pdf.ln(10)

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
            # Use multi_cell for detailed course info to handle wrapping
            pdf.multi_cell(0, 5, f"  Faculty: {row['faculty']}\n  Duration: {row['duration']}\n  Required Subjects: {row['required_subjects']}\n  Careers: {row['careers']}\n")
            pdf.ln(3) # Add small line break between courses in PDF

    print(f"DEBUG: PDF slip generated for JAMB {jamb}.")
    return pdf.output(dest='S').encode('latin-1')

# --- Gemini AI Chatbot Function ---
def get_gemini_response(user_message):
    """
    Generates a response from the Gemini API with specific context.
    Includes robust error handling and logging.
    """
    if model is None:
        print("DEBUG: Gemini model is None. Cannot generate content.")
        return "Sorry, the AI model is not available. This is a server issue. Please try again later."
    try:
        # Added a longer timeout for generate_content
        response = model.generate_content(user_message, request_options={"timeout": 60}) # 60 seconds timeout
        if response and response.text:
            print(f"DEBUG: Gemini API responded to: '{user_message[:50]}...'")
            return response.text
        else:
            print(f"DEBUG: Gemini API returned an empty or non-text response. Raw response: {response}")
            return "I received an empty response from the AI. Please try rephrasing or ask a different question."
    except Exception as e:
        print(f"ERROR: Gemini Error during content generation for message '{user_message[:50]}...': {e}")
        traceback.print_exc() # Print full traceback for Gemini errors
        return "I'm having trouble connecting to my brain right now. Please try again in a moment. (Details logged on server)"

# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles the main page and the recommendation form submission."""
    # Ensure faculties are populated even if COURSE_DATA is empty initially
    faculties = sorted(COURSE_DATA['faculty'].unique()) if not COURSE_DATA.empty else []
    results = None
    search_status = 'pending' # Initial state for status

    if request.method == 'POST':
        try:
            jamb = int(request.form['jamb'])
            subject = request.form['subject']
            faculty = request.form['faculty']

            print(f"DEBUG: Received form submission - JAMB: {jamb}, Subject: {subject}, Faculty: {faculty}")

            df_results, search_status = recommend_courses(jamb, subject, faculty)
            results = df_results.to_dict(orient='records')
            print(f"DEBUG: Recommendation returned status: {search_status}, {len(results)} results.")

        except ValueError:
            results = []
            search_status = 'not_found'
            print("ERROR: Invalid JAMB score provided. Must be a numeric value.")
        except Exception as e:
            print(f"SEARCH ERROR: An unexpected error occurred during course search: {e}")
            traceback.print_exc()
            results = []
            search_status = 'not_found'

    return render_template('index.html', results=results, faculties=faculties, status=search_status, request_form=request.form)

@app.route('/download', methods=['POST'])
def download():
    """Handles the PDF download request."""
    try:
        jamb = int(request.form['jamb'])
        subject = request.form['subject']
        faculty = request.form['faculty']

        print(f"DEBUG: Download request received - JAMB: {jamb}, Subject: {subject}, Faculty: {faculty}")

        df_results, _ = recommend_courses(jamb, subject, faculty)
        pdf_bytes = generate_pdf_slip(df_results, jamb, subject, faculty)

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'ui_recommendation_slip_{jamb}.pdf'
        )
    except Exception as e:
        print(f"PDF ERROR: Error generating PDF: {e}")
        traceback.print_exc()
        return "Error generating PDF. Please try again or contact support.", 500 # Return a 500 status code for server error

@app.route('/chat', methods=['POST'])
def chat():
    """Handles the chatbot API requests."""
    try:
        user_message = request.json.get("message")
        if not user_message:
            print("DEBUG: Chat request with empty message received.")
            return jsonify({"reply": "Please say something!"})

        bot_reply = get_gemini_response(user_message)

        print(f"DEBUG: Chatbot reply for '{user_message[:50]}...': '{bot_reply[:50]}...'")
        return jsonify({"reply": bot_reply})
    except Exception as e:
        print(f"CHAT API ERROR: An unexpected error occurred in the chat functionality: {e}")
        traceback.print_exc()
        return jsonify({"reply": "Sorry, the server ran into an internal error while processing your chat."}), 500

# --- Main Application Runner ---
if __name__ == '__main__':
    # Use 0.0.0.0 for deployment to make the server accessible externally
    # Use environment variable for PORT, default to 5000
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv("PORT", 5000)))