import os
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
import google.generativeai as genai
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

# ==============================================================================
# --- ⚙️ CONFIGURATION - UPDATE THESE VALUES ---
# ==============================================================================

# 1. Firebase Configuration
CRED_PATH = 'serviceAccountKey.json' # Path to your Firebase service account key
DATABASE_URL = 'https://nautiqal-default-rtdb.asia-southeast1.firebasedatabase.app/'
CREW_DATA_PATH = 'erp/data/shipping/fleet_management/crew-profile'
DATE_FORMAT = '%d-%b-%Y' # e.g., '03-Jul-2025'

# 2. API Keys (loaded from environment variables for security)
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# 3. Email Configuration
SENDER_EMAIL = 'genzresumebuilding@gmail.com' # The email you verified with SendGrid

# 4. Output File for the analysis report
OUTPUT_FILE = 'certification_analysis_report.json'

# ==============================================================================
# --- 🤖 LLM & ✉️ EMAIL HELPER FUNCTIONS ---
# ==============================================================================

def generate_email_body(prompt):
    """Generates email content using the Google Gemini API."""
    if not GEMINI_API_KEY:
        print("❌ ERROR: Gemini API key not configured.")
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        return None

def send_email(to_email, subject, body):
    """Sends an email using the SendGrid API."""
    if not SENDGRID_API_KEY:
        print("❌ ERROR: SendGrid API key not configured.")
        return False
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=body.replace('\n', '<br>') # Convert newlines to HTML breaks
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        if response.status_code >= 200 and response.status_code < 300:
            print(f"✅ Email successfully sent to {to_email}")
            return True
        else:
            print(f"❌ SendGrid Error: Status {response.status_code} - {response.body}")
            return False
    except Exception as e:
        print(f"❌ SendGrid Error: {e}")
        return False

# ==============================================================================
# --- 🔥 MAIN SCRIPT LOGIC ---
# ==============================================================================

def analyze_and_notify_crew():
    """Main function to run the analysis and notification process."""
    # --- 1. Initialize Firebase ---
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(CRED_PATH)
            firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
        except Exception as e:
            print(f"❌ Firebase Initialization Error: {e}")
            return

    # --- 2. Fetch Crew Data ---
    print("Fetching crew data from Firebase...")
    crew_ref = db.reference(CREW_DATA_PATH)
    all_crew_data = crew_ref.get()
    if not all_crew_data:
        print(f"⚠️ No crew data found at path: {CREW_DATA_PATH}")
        return

    # --- 3. Analyze and Process Each Crew Member ---
    now = datetime.now()
    analysis_results = {}
    print("Starting analysis and notification process...")

    for crew_id, crew_data in all_crew_data.items():
        personal_details = crew_data.get('personal_details', {})
        email = personal_details.get('email')
        name = personal_details.get('first_name', crew_id)

        if not email:
            print(f"⚠️ Skipping {crew_id}: No email address found.")
            continue
        
        print(f"\n--- Processing: {name} ({email}) ---")

        # Analyze documents
        valid_certs, expired_certs, missing_certs = [], [], []
        documents = crew_data.get('documents')
        if documents:
            for doc in documents:
                if not isinstance(doc, dict): continue
                expiry_date_str = doc.get('expiry_date')
                if not expiry_date_str:
                    missing_certs.append(doc)
                    continue
                try:
                    if datetime.strptime(expiry_date_str, DATE_FORMAT) > now:
                        valid_certs.append(doc)
                    else:
                        expired_certs.append(doc)
                except (ValueError, TypeError):
                    missing_certs.append(doc)
        
        analysis_results[email] = {
            'valid': [d.get('document_certificate', 'N/A') for d in valid_certs],
            'expired': [d.get('document_certificate', 'N/A') for d in expired_certs],
            'expiry_not_mentioned': [d.get('document_certificate', 'N/A') for d in missing_certs]
        }

        # --- 4. Generate Prompt and Send Email ---
        prompt = None
        subject = "Update on Your Certification Status"

        if expired_certs or missing_certs:
            subject = "Action Required: Update Your Certification Status"
            expired_list = "\n".join([f"- {d.get('document_certificate', 'Unknown Document')} (Expired on {d.get('expiry_date', 'N/A')})" for d in expired_certs])
            missing_list = "\n".join([f"- {d.get('document_certificate', 'Unknown Document')}" for d in missing_certs])
            
            prompt = f"""
            Write a professional and helpful email to our crew member, {name}.
            The email must clearly state the actions required for their documents.
            Maintain a supportive tone and instruct them to contact the crewing department for assistance.

            If there are expired documents, list them under a heading 'Urgent: Expired Documents'. Here is the list:
            {expired_list}

            If there are documents with missing expiry dates, list them under a heading 'Action Needed: Update Required'. Here is the list:
            {missing_list}
            """
        elif valid_certs and not expired_certs and not missing_certs:
            prompt = f"""
            Write a brief, professional, and positive email to our crew member, {name}.
            Acknowledge that a review of their documents shows all their certifications are currently up-to-date.
            Thank them for their diligence in maintaining their records.
            The tone should be encouraging.
            """
        else:
            print(f"ℹ️ Skipping email for {name}: No documents found to analyze.")
            continue

        if prompt:
            email_body = generate_email_body(prompt.strip())
            if email_body:
                send_email(email, subject, email_body)
    
    # --- 5. Save Final Report ---
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=4)
    print(f"\n✅ Process complete! Analysis report saved to '{OUTPUT_FILE}'")

# ==============================================================================
# --- 🚀 RUN THE SCRIPT ---
# ==============================================================================

if __name__ == "__main__":
    analyze_and_notify_crew()