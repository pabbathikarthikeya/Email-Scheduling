import os
import google.generativeai as genai
from dotenv import load_dotenv
# Best Practice: Store your key in an environment variable named "GEMINI_API_KEY"
# and load it like this.
# For testing, you can temporarily replace os.getenv(...) with your key in quotes.
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_PASTED_HERE")

def generate_email_body(prompt):
    """
    Generates email content using the Google Gemini API.
    """
    if not GEMINI_API_KEY or "PASTED_HERE" in GEMINI_API_KEY:
        print("❌ ERROR: Gemini API key not configured. Please set it.")
        return "Error: API key not set."
        
    try:
        # Configure the Gemini API with your key
        genai.configure(api_key=GEMINI_API_KEY)
        
        # We use 'gemini-1.5-flash' because it's fast, efficient, and great for tasks like this.
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Send the prompt to the model
        response = model.generate_content(prompt)
        
        # Return the generated text
        return response.text
        
    except Exception as e:
        print(f"❌ An error occurred with the Gemini API: {e}")
        return f"Error generating content: {e}"

# --- Example of how to use the function ---
if __name__ == "__main__":
    print("Testing the Gemini API to generate an email body...")
    
    # This is one of the prompts we designed earlier
    example_prompt = """
    Write a professional but friendly email to a crew member.
    Inform them that their 'Seaman's Book' certificate, number A0084047, has expired on 03-Jul-2025.
    Stress the importance of renewing it for compliance but maintain a supportive tone.
    Ask them to contact the crewing department for assistance.
    """
    
    # Generate the email content
    generated_body = generate_email_body(example_prompt)
    
    # Print the result
    print("\n--- Generated Email Body ---")
    print(generated_body)
    print("----------------------------")