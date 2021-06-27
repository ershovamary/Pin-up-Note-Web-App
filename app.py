from flask import Flask
from flask import render_template, abort, flash, request
from flask_bootstrap import Bootstrap

from flask_wtf import Form
from wtforms import StringField, SubmitField, BooleanField
from wtforms.validators import DataRequired

from flask_sqlalchemy import SQLAlchemy
from flask_login import current_user, login_required
from flask_security import Security, SQLAlchemyUserDatastore, \
    UserMixin, RoleMixin

import os
import wtf_helpers


class NoteForm(Form):
    note_name = StringField('Note name', validators=[Datarequired()])
    is_private = BooleanField('<mark> private </mark>')
    submit_button = SubmitField('Add note')

# Create app
app = Flask(__name__)
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
SECURITY_PASSWORD_SALT = os.urandom(42)
app.config['SECURITY_PASSWORD_SALT'] = SECURITY_PASSWORD_SALT
app.config['SECURITY_REGISTERABLE'] = True
app.config['SECURITY_SEND_REGISTER_EMAIL'] = False
app.config['SECURITY_SEND_PASSWORD_CHANGE_EMAIL'] = False
app.config['SECURITY_SEND_PASSWORD_RESET_NOTICE_EMAIL'] = False
app.config['SECURITY_FLASH_MESSAGES'] = True

# Create database connection object
db = SQLAlchemy(app)

# Define models
roles_users = db.Table('roles_users',
                       db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
                       db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))	
	notes = db.relationship('Note', backref='user', lazy='dynamic')

# Setup Flask-Security
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_name = db.Column(db.String(140))
    is_private = db.Column(db.Boolean())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, note, user):
        self.note_name = note
        self.user_id = user.id

    def __repr__(self):
        return '<Note %r>' % self.id


db.create_all()

Bootstrap(app)
wtf_helpers.add_helpers(app)


@app.route("/")
def index():
    users = User.query
    return render_template("index.html", users=users)


@app.route("/edit_note/<note_id>", methods=["GET", "POST"])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        abort(403)

    form = NoteForm()
    if request.method == "GET":
        form.is_private.data = note.is_private
        form.note_name.data = note.note_name

    if form.validate_on_submit():
        note.is_private = form.is_private.data
        note.name = form.note_name.data
        db.session.commit()
        flash("Note was changed successfully", "success")

    return render_template("edit_note.html", form=form)


@app.route("/notes/<user_email>/<privacy_filter>", methods=["GET", "POST"])
@app.route("/notes/<user_email>", defaults={'privacy_filter': 'public'}, methods=["GET", "POST"])
def notes(user_email, privacy_filter):
    user = User.query.filter_by(email=user_email).first_or_404()
    if privacy_filter == 'private' and user != current_user:
        abort(403)
    elif privacy_filter == 'private':
        is_private = True
    elif privacy_filter == 'public':
        is_private = False
    else:
        abort(404)

    if user == current_user:
        form = NoteForm()
    else:
        form = None

    if form and form.validate_on_submit():
        # TODO: populate_obj?
        note = Note(form.note_name.data, user)
        note.is_private = form.is_private.data
        form.note_name.data = ""
        db.session.add(note)
        db.session.commit()
        flash("Note was added successfully", "success")

    list_of_notes = user.notes.filter_by(is_private=is_private)
    return render_template("notes.html", form=form, list_of_notes=list_of_notes, user_email=user_email, is_private=is_private)

if __name__ == "__main__":
    app.run(debug=True)