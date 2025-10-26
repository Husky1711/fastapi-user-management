import smtplib
from email.message import EmailMessage

# Load credentials
GMAIL_USER = "psaiprasad003@gmail.com"
GMAIL_APP_PASSWORD = 'sdmdoexbksxcghzg'

def send_email_background(subject: str, recipient: str, body: str):
    """Send an email via Gmail using app password."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = recipient
    msg.set_content(body)
    
    # Add HTML content
    html_body = f"""
    <html>
        <body>
            <h2>FastAPI User Management System</h2>
            <p>{body}</p>
            <hr>
            <p style="color: gray; font-size: 12px;">This is a test email from the FastAPI system.</p>
        </body>
    </html>
    """
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Email Service")
    print("=" * 50)
    
    # Test email
    subject = "Test Email - FastAPI User Management System"
    recipient = "psaiprasad1728@gmail.com"
    body = "This is a test email from the FastAPI User Management System. If you receive this, email is working correctly!"
    
    print(f"Sending email to: {recipient}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    print()
    
    result = send_email_background(subject, recipient, body)
    
    if result:
        print("✅ Email test PASSED!")
    else:
        print("❌ Email test FAILED!")
