import os
import string
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import requests
import random
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from urllib.parse import quote


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.txt")

# OpenLibrary doesn't have a fixed list of "every genre" - it uses open-ended
# subject tags. This is a curated list of common genres that covers most
# books. Add more strings here any time you spot a genre missing.
GENRES = [
    "Fantasy", "Romance", "Science Fiction", "Thriller", "Mystery",
    "Horror", "History", "Biography", "Young Adult", "Classics",
    "Adventure", "Poetry", "Drama", "Comics", "Fiction", "Nonfiction",
    "Self-Help", "Business", "Philosophy", "Psychology", "Religion",
    "Science", "Travel", "True Crime", "Humor", "Children's Books",
    "Cooking", "Art", "Music", "Sports", "Health", "Politics", "War"
]

def book_passes_genre_filters(subjects, include_genres, exclude_genres):
    """subjects: list of subject strings from OpenLibrary for one book.
    include_genres: if non-empty, the book must match at least one.
    exclude_genres: if the book matches any of these, it's blocked."""

    subjects_lower = [s.lower() for s in subjects]

    def matches_any(genre_list):
        for genre in genre_list:
            genre_low = genre.lower()
            for subject in subjects_lower:
                if genre_low in subject:
                    return True
        return False

    if exclude_genres and matches_any(exclude_genres):
        return False

    if include_genres and not matches_any(include_genres):
        return False

    return True

def generate_captcha():

    characters = string.ascii_uppercase + string.digits

    captcha = ""

    for i in range(5):
        captcha += random.choice(characters)

    return captcha

@app.route("/captcha")
def captcha():

    text = session.get("captcha")

    if not text:
        text = generate_captcha()

    session["captcha"] = text

    width = 180
    height = 60

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        font = ImageFont.load_default()

    # Draw random lines
    for i in range(6):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)

        draw.line(
            (x1, y1, x2, y2),
            fill=(
                random.randint(100,200),
                random.randint(100,200),
                random.randint(100,200)
            ),
            width=2
        )

    # Draw letters
    x = 15

    for letter in text:

        y = random.randint(8,20)

        draw.text(
            (x,y),
            letter,
            font=font,
            fill=(
                random.randint(0,120),
                random.randint(0,120),
                random.randint(0,120)
            )
        )

        x += 30

    # Draw random dots
    for i in range(250):

        draw.point(
            (
                random.randint(0,width),
                random.randint(0,height)
            ),
            fill=(
                random.randint(0,255),
                random.randint(0,255),
                random.randint(0,255)
            )
        )

    buffer = BytesIO()

    image.save(buffer,"PNG")

    buffer.seek(0)

    return send_file(buffer,mimetype="image/png")

users = {}

with open(USERS_FILE, "r") as file:

    for line in file:

        line = line.strip()

        if line == "":
            continue

        if "," not in line:
            continue

        username, password = line.split(",", 1)

        users[username] = password

import random
import requests

def get_book_details(work_key):

    description = "Summary unavailable."

    subjects = []

    if not work_key:
        return description, subjects

    try:

        url = f"https://openlibrary.org{work_key}.json"

        response = requests.get(
            url,
            headers={"User-Agent": "BookVerse/1.0"},
            timeout=10
        )

        if response.status_code != 200:
            return description, subjects

        data = response.json()

        print(data.get("numFound"))

        print(data.get("docs")[:2])

        if "description" in data:

            if isinstance(data["description"], dict):

                description = data["description"].get(
                    "value",
                    "Summary unavailable."
                )

            elif isinstance(data["description"], str):

                description = data["description"]

        if "subjects" in data:

            subjects = data["subjects"][:6]

    except:

        pass

    return description, subjects

def get_random_book(
        genre="",
        language="",
        publication="",
        exclude_genres=None,
        random_mode=False
):

    if exclude_genres is None:
        exclude_genres = []

    if random_mode:

        genre = random.choice(GENRES)

    if genre == "":

        genre = random.choice(GENRES)

    url = (
        f"https://openlibrary.org/search.json?subject={genre}&limit=100"
        f"&fields=title,author_name,first_publish_year,language,cover_i,key,subject"
    )

    try:

        response = requests.get(

            url,

            headers={

                "User-Agent":"BookVerse/1.0"

            },

            timeout=10

        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException:

        return None

    docs = data.get("docs", [])

    # Block excluded genres first, before anything else
    if exclude_genres:

        docs = [

            book for book in docs

            if book_passes_genre_filters(book.get("subject", []), [], exclude_genres)

        ]

    if len(docs) == 0:

        return None

    filtered = []

    for book in docs:

        if language != "":

            languages = book.get("language", [])

            if language.lower() not in [

                x.lower()

                for x in languages

            ]:

                continue

        year = book.get(

            "first_publish_year",

            0

        )

        if publication == "classic":

            if year >= 2000:

                continue

        elif publication == "modern":

            if year < 2000:

                continue

        filtered.append(book)

    if len(filtered) == 0:

        filtered = docs

    if len(filtered) == 0:

        return None

    book = random.choice(filtered)

    cover = ""

    if book.get("cover_i"):

        cover = f"https://covers.openlibrary.org/b/id/{book['cover_i']}-L.jpg"

    description, subjects = get_book_details(

        book.get("key")

    )

    why = f"This recommendation matches your "

    if random_mode:

        why = "You chose a completely random recommendation."

    else:

        if genre:

            why += genre.title()

        else:

            why += "preferences"

        if publication == "classic":

            why += " and Classic publication."

        elif publication == "modern":

            why += " and Modern publication."

        else:

            why += " preference."

    return {

        "title": book.get(

            "title",

            "Unknown"

        ),

        "author": ", ".join(

            book.get(

                "author_name",

                ["Unknown"]

            )

        ),

        "year": book.get(

            "first_publish_year",

            "Unknown"

        ),

        "cover": cover,

        "description": description,

        "subjects": subjects,

        "why": why,

        "language": ", ".join(

            book.get(

                "language",

                []

            )[:3]

        )

    }

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/genre/<genre_name>')
def genre_page(genre_name):

    if "username" not in session:
        return redirect(url_for("login_page"))

    display_genre = genre_name.replace("_", " ")

    try:

        url = (
    f"https://openlibrary.org/search.json"
    f"?subject={quote(display_genre)}&limit=20"
)

        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "BookVerse/1.0"}
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException:

        return render_template(
            "results.html",
            books=[],
            error="Sorry, we couldn't reach the book service. Please try again."
        )

    books = []

    for item in data.get("docs", []):

        cover = ""

        if item.get("cover_i"):
            cover = f"https://covers.openlibrary.org/b/id/{item['cover_i']}-M.jpg"

        books.append({
            "title": item.get("title", "Unknown"),
            "author": ", ".join(item.get("author_name", ["Unknown"])),
            "thumbnail": cover
        })

    return render_template("results.html", books=books, genre=display_genre)


@app.route('/register')
def register_page():
    return render_template("register.html", error="")

@app.route('/register', methods=['POST'])
def register():

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return render_template(
            "register.html",
            error="Username and password are required."
        )

    if "," in username:
        return render_template(
            "register.html",
            error="Username cannot contain a comma."
        )

    if username in users:
        return render_template(
            "register.html",
            error="Username already exists."
        )

    hashed = generate_password_hash(password)

    users[username] = hashed

    with open(USERS_FILE, "a") as file:
        file.write(f"\n{username},{hashed}")

    return redirect(url_for("login_page"))


def verify_password(username, password):
    """Checks a password against the stored value, supporting both
    hashed (new) and legacy plaintext entries. Legacy entries get
    upgraded to a hash the moment they're verified."""

    stored = users.get(username)

    if stored is None:
        return False

    try:
        if check_password_hash(stored, password):
            return True
    except ValueError:
        # Not a valid hash string, fall through to legacy check
        pass

    if stored == password:
        # Legacy plaintext match: upgrade to a hash on the fly
        hashed = generate_password_hash(password)
        users[username] = hashed
        _rewrite_users_file()
        return True

    return False


def _rewrite_users_file():
    with open(USERS_FILE, "w") as file:
        file.write("\n".join(f"{u},{p}" for u, p in users.items()))


@app.route('/login', methods=['POST'])
def login():

    username = request.form.get('username', '')
    password = request.form.get('password', '')
    captcha = request.form.get('captcha', '')

    if captcha != session.get("captcha"):
        session["captcha"] = generate_captcha()

        return render_template(
            "login.html",
            error="Incorrect CAPTCHA!",
            captcha=session["captcha"]
        )

    if verify_password(username, password):
        session["username"] = username
        return redirect(url_for("dashboard"))

    session["captcha"] = generate_captcha()

    return render_template(
        "login.html",
        error="Invalid Username or Password.",
        captcha=session["captcha"]
    )

@app.route('/dashboard')
def dashboard():

    if "username" not in session:
        return redirect(url_for("login_page"))

    return render_template(
        "dashboard.html",
        username=session["username"]
    )

@app.route("/search", methods=["GET", "POST"])
def search():

    if "username" not in session:
        return redirect(url_for("login_page"))

    if request.method == "GET":
        return render_template("search.html", genres=GENRES)

    query = request.form.get("query", "").strip()
    include_genres = request.form.getlist("include_genres")
    exclude_genres = request.form.getlist("exclude_genres")

    # Nothing entered
    if not query and not include_genres:
        return render_template(
            "search.html",
            genres=GENRES,
            error="Please enter a search or select at least one genre."
        )

    books = []

    # Search by selected genres only
    if not query and include_genres:
        
        seen = set()
    
        for genre in include_genres:
        
            subject = quote(genre.lower())
    
            url = (
                f"https://openlibrary.org/search.json"
                f"?subject={subject}&limit=24"
                f"&fields=key,title,author_name,cover_i,subject"
            )
    
            response = requests.get(
                url,
                headers={"User-Agent": "BookVerse/1.0"},
                timeout=10
            )
    
            data = response.json()
    
            for item in data.get("docs", []):
            
                # Don't show the same book twice
                key = item.get("key")
    
                if key in seen:
                    continue
    
                seen.add(key)
    
                # Only block excluded genres
                if exclude_genres and not book_passes_genre_filters(
                    item.get("subject", []),
                    [],
                    exclude_genres
                ):
                    continue
    
                cover = ""
    
                if item.get("cover_i"):
                    cover = (
                        f"https://covers.openlibrary.org/b/id/"
                        f"{item['cover_i']}-M.jpg"
                    )
    
                books.append({
                    "title": item.get("title", "Unknown"),
                    "author": ", ".join(
                        item.get("author_name", ["Unknown"])
                    ),
                    "thumbnail": cover
                })
    
        return render_template(
            "results.html",
            books=books,
            genre=""
        )
    # Normal search
    url = (
        f"https://openlibrary.org/search.json?q={query}&limit=24"
        f"&fields=title,author_name,cover_i,subject"
    )

    response = requests.get(
        url,
        headers={"User-Agent": "BookVerse/1.0"},
        timeout=10
    )

    data = response.json()

    for item in data.get("docs", []):

        if not book_passes_genre_filters(
            item.get("subject", []),
            include_genres,
            exclude_genres
        ):
            continue

        cover = ""
        if item.get("cover_i"):
            cover = f"https://covers.openlibrary.org/b/id/{item['cover_i']}-M.jpg"

        books.append({
            "title": item.get("title", "Unknown"),
            "author": ", ".join(item.get("author_name", ["Unknown"])),
            "thumbnail": cover
        })

        if len(books) >= 20:
            break

    return render_template(
        "results.html",
        books=books,
        include_genres=include_genres,
        exclude_genres=exclude_genres,
        genre=""
    ) 

@app.route("/load_more")
def load_more():

    page = request.args.get("page", 1, type=int)
    genre = request.args.get("genre", "")

    subject = quote(genre.lower().replace(" ", "_"))

    url = (
        f"https://openlibrary.org/search.json"
        f"?subject={subject}"
        f"&limit=24"
        f"&page={page}"
        f"&fields=key,title,author_name,cover_i"
    )

    response = requests.get(
        url,
        headers={"User-Agent": "BookVerse/1.0"},
        timeout=10
    )

    data = response.json()

    books = []

    for item in data.get("docs", []):

        cover = ""

        if item.get("cover_i"):
            cover = (
                f"https://covers.openlibrary.org/b/id/"
                f"{item['cover_i']}-M.jpg"
            )

        books.append({
            "title": item.get("title", "Unknown"),
            "author": ", ".join(item.get("author_name", ["Unknown"])),
            "thumbnail": cover
        })

    return {
        "books": books
    }

@app.route("/random", methods=["GET", "POST"])
def random_book():

    if "username" not in session:
        return redirect(url_for("login_page"))

    if request.method == "POST":

        action = request.form.get("action")
        exclude_genres = request.form.getlist("exclude_genres")

        # Check if the user selected "random" or "search" mode  
        if action == "random":

            book = get_random_book(
                random_mode=True,
                exclude_genres=exclude_genres
            )

        else:

            genre = request.form.get("genre", "")
            language = request.form.get("language", "")
            publication = request.form.get("publication", "")

            book = get_random_book(
                genre=genre,
                language=language,
                publication=publication,
                exclude_genres=exclude_genres
            )

        return render_template(
            "random.html",
            book=book,
            genres=GENRES,
            selected_exclude=exclude_genres,
            searched=True
        )

    return render_template(
        "random.html",
        book=None,
        genres=GENRES,
        selected_exclude=[],
        searched=False
    )


@app.route('/login')
def login_page():

    session["captcha"] = generate_captcha()

    return render_template(
        "login.html",
        error="",
        captcha=session["captcha"]
    )

@app.route('/logout')
def logout():

    session.pop("username", None)

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)