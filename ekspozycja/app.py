from flask import Flask, render_template, request, redirect, url_for, session
from config import Config
import os
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from models import db, User, Gallery, Photo

app = Flask(__name__)
app.secret_key = 'tajny-klucz'
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



# Dane logowania "na sztywno"
USERS = {
    'admin': '1234',
    'mikolaj': 'haslo123'
}

@app.route('/')
def home():
    galleries = Gallery.query.all()
    return render_template('home.html', username=session.get('username'), galleries=galleries)



@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user is not None and user.password_hash == password:
            session['username'] = username
            return redirect(url_for('home'))
        elif username in USERS and USERS[username] == password:
            session['username'] = username
            return redirect(url_for('home'))
        else:
            error = 'Nieprawidłowy login lub hasło'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username  = request.form['username']
        password  = request.form['password']
        password2 = request.form['password2']

        # 1. Sprawdź czy hasła się zgadzają
        if password != password2:
            error = "Hasła nie są takie same"

        # 2. Sprawdź czy użytkownik już istnieje
        elif User.query.filter_by(username=username).first():
            error = "Użytkownik o tej nazwie już istnieje"

        else:
            # 3. Utwórz nowego użytkownika
            new_user = User(username=username, password_hash=password)  # NIE hashujemy
            db.session.add(new_user)
            db.session.commit()

            # 4. Zaloguj użytkownika i przekieruj na stronę główną
            session['username'] = username
            return redirect(url_for('home'))

    return render_template('register.html', error=error)



@app.route('/upload', methods=['POST'])
def upload():
    if 'photo' not in request.files:
        return redirect(url_for('home'))
    file = request.files['photo']
    if file.filename == '':
        return redirect(url_for('home'))
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    # Dodaj tutaj kod zapisu do bazy, jeśli potrzebujesz
    return redirect(url_for('home'))

@app.route('/gallery/maksiu')
def gallery_maksiu():
    return render_template('gallery_maksiu.html')

@app.route('/gallery/mikolaj')
def gallery_mikolaj():
    return render_template('gallery_mikolaj.html')

@app.route('/panel')
def user_panel():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect(url_for('logout'))  # lub inny komunikat o błędzie

    galleries = Gallery.query.filter_by(user_id=user.id).all()
    return render_template('user_panel.html', username=user.username, galleries=galleries)


@app.route('/create_gallery', methods=['POST'])
def create_gallery():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return "Błąd: Nie znaleziono użytkownika", 400

    title = request.form['title']
    album = request.form.get('album')
    files = request.files.getlist('photos')  # Uwaga! musi być 'photos'

    if title:
        gallery = Gallery(title=title, user_id=user.id)
        db.session.add(gallery)
        db.session.commit()

        for file in files:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                photo = Photo(filename=filename, gallery_id=gallery.id)
                db.session.add(photo)

        db.session.commit()

    return redirect(url_for('user_panel'))



@app.route('/gallery/<int:gallery_id>')
def view_gallery(gallery_id):
    gallery = Gallery.query.get_or_404(gallery_id)
    user = User.query.get(gallery.user_id)
    return render_template('view_gallery.html', gallery=gallery, user=user)



@app.route('/gallery/<int:gallery_id>/add_photos', methods=['POST'])
def add_photos(gallery_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    gallery = Gallery.query.get_or_404(gallery_id)
    files = request.files.getlist('photos')

    for file in files:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            photo = Photo(filename=filename, gallery_id=gallery.id)
            db.session.add(photo)

    db.session.commit()
    return redirect(url_for('view_gallery', gallery_id=gallery.id))


@app.route('/delete_photo/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    photo = Photo.query.get_or_404(photo_id)
    gallery_id = photo.gallery_id

    # Usuń plik z dysku
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    # Usuń z bazy
    db.session.delete(photo)
    db.session.commit()

    return redirect(url_for('view_gallery', gallery_id=gallery_id))

@app.route('/delete_gallery/<int:gallery_id>')
def delete_gallery(gallery_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    gallery = Gallery.query.get_or_404(gallery_id)

    # Usuń zdjęcia z dysku i bazy
    for photo in gallery.photos:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(photo)

    db.session.delete(gallery)
    db.session.commit()

    return redirect(url_for('user_panel'))

@app.route('/photo/<int:photo_id>', methods=['GET', 'POST'])
def photo_detail(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if request.method == 'POST':
        photo.title = request.form['title']
        photo.description = request.form['description']
        db.session.commit()
        return redirect(url_for('photo_detail', photo_id=photo.id))
    return render_template('photo_detail.html', photo=photo)

@app.route('/photo/<int:photo_id>/edit', methods=['GET', 'POST'])
def edit_photo(photo_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    photo = Photo.query.get_or_404(photo_id)

    if request.method == 'POST':
        photo.title = request.form['title']
        photo.description = request.form['description']
        db.session.commit()
        return redirect(url_for('view_gallery', gallery_id=photo.gallery_id))

    return render_template('edit_photo.html', photo=photo)

@app.route('/update_photo/<int:photo_id>', methods=['POST'])
def update_photo(photo_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    photo = Photo.query.get_or_404(photo_id)
    photo.title = request.form.get('title')
    photo.description = request.form.get('description')
    db.session.commit()

    return redirect(url_for('view_gallery', gallery_id=photo.gallery_id))

@app.route('/photo/<int:photo_id>/like', methods=['POST'])
def like_photo(photo_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    photo = Photo.query.get_or_404(photo_id)

    # Nie pozwól polubić 2 razy
    existing_like = Like.query.filter_by(user_id=user.id, photo_id=photo.id).first()
    if not existing_like:
        like = Like(user_id=user.id, photo_id=photo.id)
        db.session.add(like)
        db.session.commit()

    return redirect(url_for('photo_detail', photo_id=photo_id))

@app.route('/photo/<int:photo_id>/comment', methods=['POST'])
def add_comment(photo_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    content = request.form.get('content')

    if content:
        comment = Comment(content=content, user_id=user.id, photo_id=photo_id)
        db.session.add(comment)
        db.session.commit()

    return redirect(url_for('photo_detail', photo_id=photo_id))

if __name__ == '__main__':
    app.run(debug=True)


