import os
from flask import Flask, request, jsonify, render_template, redirect, url_for
from gmail_service import is_authenticated, do_auth, get_emails, get_new_emails, send_email
from ai_responder import generate_replies, categorize_email, analyze_tone
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
app.secret_key = 'gmail_ai_secret_key_123'

@app.route('/')
def home():
    authenticated = is_authenticated()
    return render_template('index.html', authenticated=authenticated)

@app.route('/auth')
def auth():
    do_auth()
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    if os.path.exists('token.json'):
        os.remove('token.json')
    return redirect(url_for('home'))

@app.route('/emails')
def emails():
    if not is_authenticated():
        return jsonify({'error': 'Not authenticated', 'requires_auth': True}), 401
    try:
        emails_list = get_emails(max_results=15)
        for email in emails_list:
            email['category'] = categorize_email(
                email.get('subject', ''),
                email.get('snippet', '')
            )
        return jsonify({'emails': emails_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate():
    if not is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    sender = data.get('sender', '')
    subject = data.get('subject', '')
    body = data.get('body', '')
    user_name = data.get('user_name', 'Haseeb')
    user_role = data.get('user_role', 'AI Developer')
    user_company = data.get('user_company', '')

    if not body and not subject:
        return jsonify({'error': 'No email content provided'}), 400

    try:
        replies = generate_replies(sender, subject, body, user_name, user_role, user_company)
        return jsonify({'replies': replies})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/send', methods=['POST'])
def send():
    if not is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    to = data.get('to', '')
    subject = data.get('subject', '')
    body = data.get('body', '')
    thread_id = data.get('thread_id', None)
    message_id = data.get('message_id', None)

    if not to or not body:
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        send_email(to, subject, body, thread_id=thread_id, message_id=message_id)
        return jsonify({'message': '✅ Email sent successfully!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/poll')
def poll():
    if not is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        since_id = request.args.get('since_id', None)
        new_emails = get_new_emails(since_id=since_id, max_results=5)
        for email in new_emails:
            email['category'] = categorize_email(
                email.get('subject', ''),
                email.get('snippet', '')
            )
        return jsonify({'emails': new_emails})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/mark-read', methods=['POST'])
def mark_read():
    if not is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    thread_id = data.get('message_id')
    if not thread_id:
        return jsonify({'error': 'No thread_id provided'}), 400
    try:
        from gmail_service import mark_as_read
        mark_as_read(thread_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analyze', methods=['POST'])
def analyze():
    if not is_authenticated():
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    subject = data.get('subject', '')
    body = data.get('body', '')
    try:
        result = analyze_tone(subject, body)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)