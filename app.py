from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
import requests as http_client
from datetime import datetime, timezone
import re
import json as json_lib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secure-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

# OpenRouter AI config
OPENROUTER_API_KEY = "API"
OPENROUTER_MODEL = "openrouter/free"

# Site owner username — this user can view messages from other users
ADMIN_USERNAME = "manu"

# System prompt — tells the AI what tools it has
SYSTEM_PROMPT = """You are Emmanuel Kibet's personal AI assistant on his portfolio website. Your job is to help visitors learn about him, navigate his portfolio, and contact him.

Emmanuel's Socials:
- LinkedIn: [Emmanuel Kibet](https://www.linkedin.com/in/emmanuel-kibet-31848a38b/)
- X (Twitter): [3_mmanv3l](https://x.com/3_mmanv3l)
- Instagram: [3_mma_nv3l](https://www.instagram.com/3_mma_nv3l/)
- WakaTime: [Convexkarma](https://wakatime.com/@Convexkarma)

If a user asks for social media links, provide them using standard markdown format: [Platform](URL).

You can perform actions by including a JSON block wrapped in <action></action> tags in your response.

AVAILABLE ACTIONS:
1. Message the owner(Emmanuel Kibet): <action>{{"type":"send_message","message":"MESSAGE_TEXT"}}</action>
2. Navigate to page:  <action>{{"type":"navigate","page":"PAGE_NAME"}}</action>
   Valid pages: home, dashboard, messages

RULES:
- Only include an <action> tag when the user EXPLICITLY asks to perform an action.
- Always include a friendly text response alongside any action.
- For normal conversation, just respond helpfully without any action tags.
- Be concise, professional, and friendly.
- Format links beautifully using markdown: [Link Text](https://link.com)

EASTER EGGS (SECRET COMMANDS):
- If the user asks you to "make me rich", "build an app that makes $1M/month", or something similar, reply EXACTLY with: "I'll get right on that. 🚀" and include this action: <action>{{"type":"meme_chad"}}</action>
- If the user types "fsociety" or "Hello friend", reply EXACTLY with: "Hello, friend. Are you a 1 or a 0?" and include this action: <action>{{"type":"meme_fsociety"}}</action>
- If the user types "take me back", "light mode", "normal mode", or similar, reply EXACTLY with: "Reverting to standard protocol. Welcome back." and include this action: <action>{{"type":"meme_normal"}}</action>

CURRENT USER: {username}
"""

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ── Models ──────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_name = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    link = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    date = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class LifestyleImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


with app.app_context():
    db.create_all()
    # Seed admin user if it doesn't exist
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(username=ADMIN_USERNAME).first():
        hashed_pw = generate_password_hash("changeme123", method='pbkdf2:sha256')
        admin = User(username=ADMIN_USERNAME, password=hashed_pw)
        db.session.add(admin)
        db.session.commit()

    # Seed original events if empty
    if Event.query.count() == 0:
        events = [
            Event(title='Meeting Dr. Bright Gameli', date='Tech Leadership & Mentorship', description='Had the honor of connecting with Dr. Bright Gameli, a leading figure in African cybersecurity. An incredible opportunity to discuss the future of tech, security, and innovation on the continent alongside my friend Robert.', image_url='/static/pic6.jpeg'),
            Event(title='Safaricom Decode Event', date='"Made of Kenya Edition"', description='Attended the Safaricom Decode event, diving deep into homegrown technological solutions and networking with Kenya\'s brightest engineers and innovators.', image_url='/static/pic8.jpeg'),
            Event(title='Kenya School of Law Hackathon', date='Cybersecurity Enthusiasts', description='Collaborated with a brilliant group of cybersecurity enthusiasts during an intense hackathon at the Kenya School of Law, solving complex security challenges and building resilient systems.', image_url='/static/pic10.jpeg')
        ]
        db.session.bulk_save_objects(events)
        db.session.commit()

    # Seed original skills if empty
    if Skill.query.count() == 0:
        skills = [
            Skill(name='Python'),
            Skill(name='Flask'),
            Skill(name='Artificial Intelligence (LLMs)'),
            Skill(name='Kali Linux'),
            Skill(name='Nmap'),
            Skill(name='Proxychains'),
            Skill(name='John the Ripper'),
            Skill(name='Cybersecurity Operations')
        ]
        db.session.bulk_save_objects(skills)
        db.session.commit()


# ── AI Helpers ──────────────────────────────────────────

def parse_ai_response(text):
    """Extract action JSON and clean text from AI response."""
    action = None
    match = re.search(r'<action>(.*?)</action>', text, re.DOTALL)
    if match:
        try:
            action = json_lib.loads(match.group(1).strip())
        except (json_lib.JSONDecodeError, ValueError):
            pass
    clean = re.sub(r'<action>.*?</action>', '', text, flags=re.DOTALL).strip()
    return clean, action


def execute_action(action, user):
    """Execute a parsed action. Returns (result_message, frontend_action)."""
    atype = action.get("type")

    if atype == "send_message":
        msg_content = action.get("message", "").strip()
        if not msg_content:
            return "Message cannot be empty.", None
        msg = Message(sender_id=user.id, sender_name=user.username, content=msg_content)
        db.session.add(msg)
        db.session.commit()
        return "Message sent to the site owner.", None

    elif atype == "navigate":
        page = action.get("page", "dashboard")
        url_map = {
            "home": url_for('home'),
            "dashboard": url_for('dashboard'),
            "messages": url_for('messages'),
            "profile": url_for('profile'),
        }
        url = url_map.get(page, url_for('dashboard'))
        return None, {"type": "navigate", "url": url}

    elif atype in ["meme_chad", "meme_fsociety", "meme_normal"]:
        return None, {"type": atype}

    return None, None


# ── Routes ──────────────────────────────────────────────

@app.route("/")
def home():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    events = Event.query.order_by(Event.created_at.desc()).all()
    lifestyle_images = LifestyleImage.query.order_by(LifestyleImage.created_at.desc()).all()
    skills = Skill.query.order_by(Skill.created_at.asc()).all()
    return render_template("home.html", projects=projects, events=events, lifestyle_images=lifestyle_images, skills=skills)


@app.route('/add_project', methods=['POST'])
@login_required
def add_project():
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    title = request.form.get('title')
    description = request.form.get('description')
    image_url = request.form.get('image_url')
    link = request.form.get('link')
    
    new_project = Project(title=title, description=description, image_url=image_url, link=link)
    db.session.add(new_project)
    db.session.commit()
    flash("Project added successfully!")
    return redirect(url_for('dashboard'))

@app.route('/add_event', methods=['POST'])
@login_required
def add_event():
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    title = request.form.get('title')
    description = request.form.get('description')
    image_url = request.form.get('image_url')
    date = request.form.get('date')
    
    new_event = Event(title=title, description=description, image_url=image_url, date=date)
    db.session.add(new_event)
    db.session.commit()
    flash("Event added successfully!")
    return redirect(url_for('dashboard'))

@app.route('/edit_event/<int:event_id>', methods=['POST'])
@login_required
def edit_event(event_id):
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    event = Event.query.get_or_404(event_id)
    event.title = request.form.get('title')
    event.description = request.form.get('description')
    event.image_url = request.form.get('image_url')
    event.date = request.form.get('date')
    db.session.commit()
    flash("Event updated successfully!")
    return redirect(url_for('dashboard'))

@app.route('/delete_event/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Event removed.', 'success')
    return redirect(url_for('dashboard'))

# ── Skills CMS ──────────────────────────────────────────

@app.route("/admin/skill/add", methods=["POST"])
@login_required
def add_skill():
    name = request.form.get('name')
    if name:
        new_skill = Skill(name=name)
        db.session.add(new_skill)
        db.session.commit()
        flash('Skill added successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route("/admin/skill/delete/<int:skill_id>", methods=["POST"])
@login_required
def delete_skill(skill_id):
    skill = Skill.query.get(skill_id)
    if skill:
        db.session.delete(skill)
        db.session.commit()
        flash('Skill removed.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/add_lifestyle', methods=['POST'])
@login_required
def add_lifestyle():
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    image_url = request.form.get('image_url')
    caption = request.form.get('caption')
    
    new_img = LifestyleImage(image_url=image_url, caption=caption)
    db.session.add(new_img)
    db.session.commit()
    flash("Lifestyle photo added successfully!")
    return redirect(url_for('dashboard'))

@app.route('/edit_lifestyle/<int:img_id>', methods=['POST'])
@login_required
def edit_lifestyle(img_id):
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    img = LifestyleImage.query.get_or_404(img_id)
    img.image_url = request.form.get('image_url')
    img.caption = request.form.get('caption')
    db.session.commit()
    flash("Lifestyle photo updated successfully!")
    return redirect(url_for('dashboard'))

@app.route('/delete_lifestyle/<int:img_id>', methods=['POST'])
@login_required
def delete_lifestyle(img_id):
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    img = LifestyleImage.query.get_or_404(img_id)
    db.session.delete(img)
    db.session.commit()
    flash("Lifestyle photo deleted successfully!")
    return redirect(url_for('dashboard'))

@app.route('/edit_project/<int:project_id>', methods=['POST'])
@login_required
def edit_project(project_id):
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    project = Project.query.get_or_404(project_id)
    project.title = request.form.get('title')
    project.description = request.form.get('description')
    project.image_url = request.form.get('image_url')
    project.link = request.form.get('link')
    db.session.commit()
    flash("Project updated successfully!")
    return redirect(url_for('dashboard'))

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    if current_user.username != ADMIN_USERNAME:
        flash("Unauthorized.")
        return redirect(url_for('dashboard'))
    
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted successfully!")
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            user.login_count = (user.login_count or 0) + 1
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    unread = 0
    is_admin = current_user.username == ADMIN_USERNAME
    if is_admin:
        unread = Message.query.filter_by(is_read=False).count()
    projects = Project.query.order_by(Project.created_at.desc()).all()
    events = Event.query.order_by(Event.created_at.desc()).all()
    lifestyle_images = LifestyleImage.query.order_by(LifestyleImage.created_at.desc()).all()
    skills = Skill.query.order_by(Skill.created_at.asc()).all()
    return render_template(
        'dashboard.html',
        name=current_user.username,
        login_count=current_user.login_count or 0,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        is_admin=is_admin,
        unread_count=unread,
        projects=projects,
        events=events,
        lifestyle_images=lifestyle_images,
        skills=skills
    )


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_username':
            new_name = request.form.get('new_username', '').strip()
            if len(new_name) < 3:
                flash('Username must be at least 3 characters.')
            elif User.query.filter_by(username=new_name).first():
                flash('Username already taken.')
            else:
                current_user.username = new_name
                db.session.commit()
                flash('Username updated successfully!')
        elif action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            if not check_password_hash(current_user.password, current_pw):
                flash('Current password is incorrect.')
            elif len(new_pw) < 6:
                flash('New password must be at least 6 characters.')
            else:
                current_user.password = generate_password_hash(new_pw, method='pbkdf2:sha256')
                db.session.commit()
                flash('Password updated successfully!')
        elif action == 'delete_account':
            db.session.delete(current_user)
            db.session.commit()
            logout_user()
            flash('Your account has been successfully deleted.')
            return redirect(url_for('home'))
        return redirect(url_for('profile'))
    return render_template(
        'profile.html',
        user=current_user,
        msg_count=Message.query.filter_by(sender_id=current_user.id).count(),
    )


@app.route('/messages')
@login_required
def messages():
    is_admin = current_user.username == ADMIN_USERNAME
    if is_admin:
        msgs = Message.query.order_by(Message.created_at.desc()).all()
        Message.query.filter_by(is_read=False).update({"is_read": True})
        db.session.commit()
    else:
        msgs = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).all()
    return render_template('messages.html', messages=msgs, is_admin=is_admin)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have logged out.')
    return redirect(url_for('login'))


# ── AI Chat (with tool use) ────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    history = data.get("history", [])
    user_msg = data.get("message", "")
    
    if user_msg:
        conversation = history + [{"role": "user", "content": user_msg}]
    else:
        conversation = history

    # Build API messages with system prompt
    username = current_user.username if current_user.is_authenticated else "Visitor"
    system_msg = SYSTEM_PROMPT.format(username=username)
    api_messages = [{"role": "system", "content": system_msg}] + conversation

    try:
        res = http_client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": api_messages,
            },
            timeout=30,
        )
        res.raise_for_status()
        raw_reply = res.json()["choices"][0]["message"]["content"]

        # Parse response for action tags
        clean_reply, action = parse_ai_response(raw_reply)

        frontend_action = None
        if action:
            result_msg, frontend_action = execute_action(action, current_user)
            if result_msg:
                clean_reply = (clean_reply + "\n\n✅ " + result_msg) if clean_reply else ("✅ " + result_msg)

        response = {"reply": clean_reply or "Done!"}
        if frontend_action:
            response["action"] = frontend_action
        return jsonify(response)

    except Exception as e:
        return jsonify({"reply": f"⚠️ AI error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
