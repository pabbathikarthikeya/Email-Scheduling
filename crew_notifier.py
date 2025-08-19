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
# --- ⚙️ CONFIGURATION ---
# ==============================================================================

# This loads environment variables from a .env file for local testing
load_dotenv() 

# 1. Firebase Configuration
CRED_PATH = 'serviceAccountKey.json'
DATABASE_URL = os.getenv('DATABASE_URL')
CREW_DATA_PATH = os.getenv('CREW_DATA_PATH')
DATE_FORMAT = '%d-%b-%Y' # e.g., '19-Aug-2025'

# 2. API Keys (loaded from environment variables)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# 3. Email Configuration
SENDER_EMAIL = os.getenv("SENDER_EMAIL") 

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
    # Convert newlines to HTML breaks for better email formatting
    html_body = body.replace('\n', '<br>')
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html_body
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        if 200 <= response.status_code < 300:
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
    """Main function to run the analysis and smart notification process."""
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
    print("Starting analysis and smart notification process...")

    for crew_id, crew_data in all_crew_data.items():
        personal_details = crew_data.get('personal_details', {})
        email = personal_details.get('email')
        name = personal_details.get('first_name', crew_id)

        if not email:
            print(f"⚠️ Skipping {crew_id}: No email address found.")
            continue
        
        print(f"\n--- Processing: {name} ({email}) ---")

        expired_certs_to_notify = []
        documents = crew_data.get('documents')
        if not documents:
            print(f"ℹ️ Skipping {name}: No documents found.")
            continue

        for doc in documents:
            if not isinstance(doc, dict): continue
            
            expiry_date_str = doc.get('expiry_date')
            doc_number = doc.get('document_number')
            
            # Check if the certificate is expired
            is_expired = False
            if expiry_date_str:
                try:
                    if datetime.strptime(expiry_date_str, DATE_FORMAT) < now:
                        is_expired = True
                except (ValueError, TypeError):
                    continue # Skip malformed dates

            if is_expired:
                # This is the "smart" part: check if we already sent a notification
                if not doc_number:
                    print(f"⚠️ Skipping expired doc '{doc.get('document_certificate')}' for {name}: No document number to track notification status.")
                    continue

                # Create a safe ID for the Firebase path
                safe_doc_number = doc_number.replace('.', '_').replace('/', '_').replace('#', '_')
                notification_id = f"EXPIRED_{safe_doc_number}"
                log_ref = db.reference(f"{CREW_DATA_PATH}/{crew_id}/notification_log/{notification_id}")

                if log_ref.get() is None:
                    print(f"✅ NEW expired cert found for {name}: {doc.get('document_certificate')}")
                    expired_certs_to_notify.append(doc)
                else:
                    print(f"ℹ️ Skipping email for {name}: Notification for {doc.get('document_certificate')} already sent.")

        # --- 4. Generate a single prompt for all new expired certs and send email ---
        if expired_certs_to_notify:
            subject = "Urgent: Action Required on Expired Certifications"
            expired_list = "\n".join([f"- {d.get('document_certificate', 'Unknown')} (Expired on {d.get('expiry_date', 'N/A')})" for d in expired_certs_to_notify])
            
            prompt = f"""
            Write a professional and helpful email to our crew member, {name}.
            The email must clearly state that some of their documents have expired and require urgent attention.
            Maintain a supportive tone and instruct them to contact the crewing department for assistance with renewal.

            List the expired documents clearly under a heading 'Urgent: Expired Documents'. Here is the list:
            {expired_list}
            """
            
            email_body = generate_email_body(prompt.strip())
            
            if email_body and send_email(email, subject, email_body):
                # If email is sent successfully, log it in Firebase for each document
                for doc in expired_certs_to_notify:
                    doc_number = doc.get('document_number')
                    safe_doc_number = doc_number.replace('.', '_').replace('/', '_').replace('#', '_')
                    notification_id = f"EXPIRED_{safe_doc_number}"
                    log_ref = db.reference(f"{CREW_DATA_PATH}/{crew_id}/notification_log/{notification_id}")
                    log_ref.set(datetime.now().strftime("%Y-%m-%d"))
                print(f"Successfully logged notifications for {name}.")
            else:
                print(f"❌ Failed to send email to {name}. Notification will be attempted again on next run.")

    print("\n✅ Process complete!")


# ==============================================================================
# --- 🚀 RUN THE SCRIPT ---
# ==============================================================================

if __name__ == "__main__":
    analyze_and_notify_crew()