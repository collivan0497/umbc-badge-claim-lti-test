import os
import json
import requests
from flask import Flask, request, render_template_string, redirect, url_for, session
from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest, FlaskCacheDataStorage
from pylti1p3.deep_link_resource import DeepLinkResource
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.lineitem import LineItem
from cachelib import SimpleCache

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL', '')

cache = SimpleCache()

PAGE_STYLE = '''
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
        font-size: 20px;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 28px;
        padding-bottom: 20px;
        border-bottom: 2px solid #f0f0f0;
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
    .error {
        background: #fff0f0;
        border: 1px solid #ffcccc;
        color: #cc0000;
        padding: 14px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
        font-size: 14px;
    }
    .checkmark { font-size: 56px; margin-bottom: 20px; text-align: center; }
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
'''

CONFIRMATION_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Badge Claim Confirmation</title>
    ''' + PAGE_STYLE + '''
</head>
<body>
    <div class="card">
        <div class="umbc-header">UMBC Microcredential Claim</div>
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

SUCCESS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Badge Claim Submitted</title>
    ''' + PAGE_STYLE + '''
</head>
<body>
    <div class="card" style="text-align:center">
        <div class="checkmark">🎉</div>
        <h2>Claim Submitted!</h2>
        <div class="badge-name">{{ badge_name }}</div>
        <p style="font-size:15px;color:#666;line-height:1.6">Your badge claim has been received. Your digital microcredential will be issued to your UMBC email address within 24 hours.</p>
    </div>
</body>
</html>
'''

ERROR_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    ''' + PAGE_STYLE + '''
</head>
<body>
    <div class="card">
        <div class="umbc-header">UMBC Microcredential Claim</div>
        <div class="error">{{ error }}</div>
        <p style="font-size:14px;color:#666">Please contact your instructor or <a href="mailto:csulli1@umbc.edu">csulli1@umbc.edu</a> for assistance.</p>
    </div>
</body>
</html>
'''

def get_tool_conf():
    config_file = os.path.join(os.path.dirname(__file__), 'lti_config.json')
    return ToolConfJsonFile(config_file)

def get_launch_data_storage():
    return FlaskCacheDataStorage(cache)

DEEP_LINK_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configure Badge</title>
''' + PAGE_STYLE + '''
</head>
<body>
    <div class="card">
        <div class="umbc-header">UMBC Microcredential — Configure Badge Link</div>
        <h2>Set Badge for This Link</h2>
        <p class="subtitle">This configuration is for instructors only. Students will not see this screen.</p>
        <form method="POST" action="/deep_link_return">
            <input type="hidden" name="jwt" value="{{ jwt }}">
            <div class="field" style="background:white;padding:0;margin-bottom:16px">
                <label class="field-label" style="display:block;margin-bottom:6px">Badge Name</label>
                <input type="text" name="badge_name" placeholder="e.g. Python Programming Badge"
                    style="width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:15px">
            </div>
            <div class="field" style="background:white;padding:0;margin-bottom:16px">
                <label class="field-label" style="display:block;margin-bottom:6px">Badge ID</label>
                <input type="text" name="badge_id" placeholder="e.g. 20260429python"
                    style="width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:15px">
            </div>
            <button type="submit" class="submit-btn">Save Badge Configuration</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/deep_link_return', methods=['POST'])
def deep_link_return():
    jwt = request.form.get('jwt')
    badge_name = request.form.get('badge_name', 'Unknown Badge')
    badge_id = request.form.get('badge_id', 'unknown')

    tool_conf = get_tool_conf()
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()

    try:
        message_launch = FlaskMessageLaunch.from_cache(jwt, flask_request, tool_conf, launch_data_storage=launch_data_storage)
        deep_link = message_launch.get_deep_link()
        resource = DeepLinkResource()
        resource.set_url(f"https://umbc-badge-claim-lti-test-production.up.railway.app/launch")
        resource.set_custom_params({'badge_name': badge_name, 'badge_id': badge_id})
        resource.set_title(badge_name)
        html = deep_link.output_response_form([resource])
        return html
    except Exception as e:
        return render_template_string(ERROR_TEMPLATE, error=f"Deep link error: {str(e)}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    tool_conf = get_tool_conf()
    launch_data_storage = get_launch_data_storage()
    flask_request = FlaskRequest()
    target_link_uri = flask_request.get_param('target_link_uri')
    if not target_link_uri:
        raise Exception('Missing "target_link_uri" param')
    oidc_login = FlaskOIDCLogin(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    return oidc_login.enable_check_cookies().redirect(target_link_uri)

@app.route('/launch', methods=['POST'])
def launch():
    tool_conf = get_tool_conf()
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    
    try:
        message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
        message_launch_data = message_launch.get_launch_data()
        # Handle deep linking launch (instructor configuration)
        if message_launch.is_deep_link_launch():
            jwt = message_launch.get_launch_id()
            return render_template_string(DEEP_LINK_TEMPLATE, jwt=jwt)
    except Exception as e:
        return render_template_string(ERROR_TEMPLATE, error=f"Launch error: {str(e)}")

    # Extract user info from LTI 1.3 launch data
    first_name = message_launch_data.get('given_name', 
                  message_launch_data.get('name', 'Unknown').split(' ')[0])
    last_name = message_launch_data.get('family_name',
                 ' '.join(message_launch_data.get('name', 'Unknown').split(' ')[1:]))
    email = message_launch_data.get('email', 'Unknown')
    
    # Course info
    context = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/context', {})
    course_id = context.get('id', 'Unknown')
    course_name = context.get('title', 'Unknown')
    
    # Custom parameters - set per LTI placement in Blackboard
    custom = message_launch_data.get('https://purl.imsglobal.org/spec/lti/claim/custom', {})
    badge_name = custom.get('badge_name', 'Unknown Badge')
    badge_id = custom.get('badge_id', 'Unknown')
    campus_id = custom.get('lis_person_sourcedid', message_launch_data.get('sub', 'Unknown'))

    return render_template_string(CONFIRMATION_TEMPLATE,
        first_name=first_name,
        last_name=last_name,
        email=email,
        campus_id=campus_id,
        course_id=course_id,
        course_name=course_name,
        badge_name=badge_name,
        badge_id=badge_id
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

    return render_template_string(SUCCESS_TEMPLATE, badge_name=data['badge_name'])

@app.route('/health')
def health():
    return {'status': 'ok'}

@app.route('/.well-known/jwks.json')
def jwks():
    tool_conf = get_tool_conf()
    return tool_conf.get_jwks()

if __name__ == '__main__':
    app.run(debug=True)
