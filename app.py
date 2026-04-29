from flask import Flask, request, jsonify, render_template_string
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Google Apps Script Web App URL - set this as environment variable
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', '')

CONFIRMATION_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Badge Claim Confirmation</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 2px 16px rgba(0,0,0,0.08);
        }
        .umbc-header {
            display: flex;
            align-items: center;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }
        .umbc-header span {
            font-size: 20px;
            font-weight: 700;
            color: #1a1a1a;
        }
        h2 { font-size: 18px; color: #1a1a1a; margin-bottom: 8px; }
        .subtitle { font-size: 14px; color: #666; margin-bottom: 28px; }
        .field {
            background: #f8f8f8;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 10px;
        }
        .field-label {
            font-size: 11px;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .field-value { font-size: 15px; color: #1a1a1a; font-weight: 500; }
        .badge-field { background: #f0f4ff; border: 1px solid #d0dbff; }
        .badge-field .field-value { color: #2d4fd6; }
        .submit-btn {
            width: 100%;
            background: #1a1a1a;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 16px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 24px;
            transition: background 0.2s;
        }
        .submit-btn:hover { background: #333; }
        .disclaimer {
            font-size: 12px;
            color: #999;
            text-align: center;
            margin-top: 14px;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="umbc-header">
            <span>UMBC Microcredential Claim</span>
        </div>
        <h2>Badge Claim Confirmation</h2>
        <p class="subtitle">Please review your information before submitting.</p>
        <div class="field">
            <div class="field-label">Name</div>
            <div class="field-value">{{ first_name }} {{ last_name }}</div>
        </div>
        <div class="field">
            <div class="field-label">Email</div>
            <div class="field-value">{{ email }}</div>
        </div>
        <div class="field">
            <div class="field-label">Campus ID</div>
            <div class="field-value">{{ campus_id }}</div>
        </div>
        <div class="field">
            <div class="field-label">Course</div>
            <div class="field-value">{{ course_name }}</div>
        </div>
        <div class="field badge-field">
            <div class="field-label">Badge Being Claimed</div>
            <div class="field-value">{{ badge_name }}</div>
        </div>
        <form method="POST" action="/submit">
            <input type="hidden" name="first_name" value="{{ first_name }}">
            <input type="hidden" name="last_name" value="{{ last_name }}">
            <input type="hidden" name="email" value="{{ email }}">
            <input type="hidden" name="campus_id" value="{{ campus_id }}">
            <input type="hidden" name="course_id" value="{{ course_id }}">
            <input type="hidden" name="course_name" value="{{ course_name }}">
            <input type="hidden" name="badge_name" value="{{ badge_name }}">
            <input type="hidden" name="badge_id" value="{{ badge_id }}">
            <button type="submit" class="submit-btn">Confirm & Claim Badge</button>
        </form>
        <p class="disclaimer">By submitting, you confirm that you have met the earning criteria for this badge. This claim will be reviewed before your badge is issued.</p>
    </div>
</body>
</html>
'''

SUCCESS_PAGE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Badge Claim Submitted</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 2px 16px rgba(0,0,0,0.08);
            text-align: center;
        }
        .checkmark { font-size: 56px; margin-bottom: 20px; }
        h2 { font-size: 22px; color: #1a1a1a; margin-bottom: 12px; }
        p { font-size: 15px; color: #666; line-height: 1.6; }
        .badge-name {
            display: inline-block;
            background: #f0f4ff;
            border: 1px solid #d0dbff;
            color: #2d4fd6;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 20px;
            margin: 16px 0;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="checkmark">🎉</div>
        <h2>Claim Submitted!</h2>
        <div class="badge-name">{{ badge_name }}</div>
        <p>Your badge claim has been received. Your digital microcredential will be issued to your UMBC email address within 24 hours.</p>
    </div>
</body>
</html>
'''

@app.route('/launch', methods=['POST'])
def launch():
    first_name = request.form.get('lis_person_name_given', request.form.get('given_name', 'Unknown'))
    last_name = request.form.get('lis_person_name_family', request.form.get('family_name', 'Unknown'))
    email = request.form.get('lis_person_contact_email_primary', request.form.get('email', 'Unknown'))
    campus_id = request.form.get('lis_person_sourcedid', request.form.get('ext_user_username', 'Unknown'))
    course_id = request.form.get('context_id', 'Unknown')
    course_name = request.form.get('context_title', 'Unknown')
    badge_name = request.form.get('custom_badge_name', 'Unknown Badge')
    badge_id = request.form.get('custom_badge_id', 'Unknown')

    return render_template_string(CONFIRMATION_PAGE,
        first_name=first_name,
        last_name=last_name,
        email=email,
        campus_id=campus_id,
        course_id=course_id,
        course_name=course_name,
        badge_name=badge_name,
        badge_id=badge_id,
        error=None
    )

@app.route('/submit', methods=['POST'])
def submit():
    data = {
        'first_name': request.form.get('first_name'),
        'last_name': request.form.get('last_name'),
        'email': request.form.get('email'),
        'campus_id': request.form.get('campus_id'),
        'course_id': request.form.get('course_id'),
        'course_name': request.form.get('course_name'),
        'badge_name': request.form.get('badge_name'),
        'badge_id': request.form.get('badge_id'),
    }

    try:
        response = requests.post(GOOGLE_SHEET_URL, json=data, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Error posting to Google Sheet: {e}")

    return render_template_string(SUCCESS_PAGE, badge_name=data['badge_name'])

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
