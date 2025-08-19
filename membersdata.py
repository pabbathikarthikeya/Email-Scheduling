import json
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

# --- Configuration ---
# 1. Path to your service account key file
CRED_PATH = 'serviceAccountKey.json' # <-- IMPORTANT: UPDATE THIS PATH

# 2. Your Realtime Database URL
DATABASE_URL = 'https://nautiqal-default-rtdb.asia-southeast1.firebasedatabase.app/' # <-- UPDATE WITH YOUR URL

# 3. Path to the crew profiles in your database
CREW_DATA_PATH = 'erp/data/shipping/fleet_management/crew-profile'

# 4. Assumed date format in your database (e.g., Day-Month-Year)
#    IMPORTANT: Change this if your date format is different (e.g., 'YYYY-MM-DD')
DATE_FORMAT = '%d-%b-%Y'

# 5. Output file name
OUTPUT_FILE = 'certification_analysis.json'
# --- End Configuration ---


def analyze_crew_certifications():
    """
    Fetches crew data from Firebase and categorizes their document certifications
    based on expiry dates.
    """
    try:
        # Initialize the Firebase Admin SDK
        cred = credentials.Certificate(CRED_PATH)
        firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        return

    # Get a reference to all crew profiles
    crew_ref = db.reference(CREW_DATA_PATH)
    all_crew_data = crew_ref.get()

    if not all_crew_data:
        print("⚠️ No crew data found at the specified path.")
        return

    # Get the current date and time
    now = datetime.now()
    
    # This dictionary will hold the final categorized results
    analysis_results = {}

    print("🚀 Starting analysis of crew certifications...")

    # Loop through each crew member in the database
    for crew_id, crew_data in all_crew_data.items():
        # Get crew member's email, use crew_id as a fallback
        personal_details = crew_data.get('personal_details', {})
        email = personal_details.get('email', f"no-email-found-for-{crew_id}")

        analysis_results[email] = {
            'valid': [],
            'expired': [],
            'expiry_not_mentioned': []
        }

        # Get the list of documents, handle cases where it might be missing
        documents = crew_data.get('documents')
        if not documents:
            continue # Skip to the next crew member if they have no documents

        # Loop through each document/certification
        for doc in documents:
            if not isinstance(doc, dict):
                continue # Skip if the item in the list is not a dictionary

            expiry_date_str = doc.get('expiry_date')

            # Case 1: Expiry date is missing, empty, or None
            if not expiry_date_str:
                analysis_results[email]['expiry_not_mentioned'].append(doc)
                continue

            # Case 2: Try to parse and compare the date
            try:
                expiry_date_obj = datetime.strptime(expiry_date_str, DATE_FORMAT)
                if expiry_date_obj > now:
                    # VALID: Expiry is in the future
                    analysis_results[email]['valid'].append(doc)
                else:
                    # EXPIRED: Expiry is in the past
                    analysis_results[email]['expired'].append(doc)
            except (ValueError, TypeError):
                # INVALID FORMAT: Date string is not in the expected format
                analysis_results[email]['expiry_not_mentioned'].append(doc)

    # Save the results to a JSON file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ Analysis complete! Results saved to '{OUTPUT_FILE}'")
    
    # Optional: Print a summary to the console
    print("\n--- Summary ---")
    for email, data in analysis_results.items():
        print(f"👤 {email}:")
        print(f"  - Valid: {len(data['valid'])} certificate(s)")
        print(f"  - Expired: {len(data['expired'])} certificate(s)")
        print(f"  - Expiry Not Mentioned: {len(data['expiry_not_mentioned'])} certificate(s)")
        print("-" * 20)

# Run the analysis function
if __name__ == "__main__":
    analyze_crew_certifications()