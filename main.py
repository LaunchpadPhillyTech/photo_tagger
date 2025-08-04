### - Libraries - ###
from flask import Flask, render_template, request, redirect, session, abort, flash
import os
import re
import sqlite3
import json
import datetime


from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import googleapiclient.discovery
from googleapiclient.discovery import build


### - Flask App Setup - ###
app = Flask(__name__)
app.secret_key = os.urandom(24)


### - Configuration Constants - ###
# User Access Control
ALLOWED_USERS = {
    "alope0091@launchpadphilly.org",
    "rob@launchpadphilly.org",
    "melanie@b-21.org"
}

# Database Configuration
DB_FILE = "data/data.db"

# Pagination Settings
DEFAULT_PAGE = 1
ITEMS_PER_PAGE = 40

# Google OAuth Configuration
OAUTH_REDIRECT_URI = "https://6be0ea6f-d348-44dd-942f-ec161e8d1061-00-2rqrh2hfqtnar.picard.replit.dev/oauth2callback"
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]
CREDENTIALS_FILE = "credentials.json"

# Server Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8080

# API Settings
GOOGLE_DRIVE_API_VERSION = "v3"
OAUTH2_API_VERSION = "v2"

# URL Patterns
DRIVE_FILE_ID_PATTERN = r"/d/([a-zA-Z0-9_-]+)"
DRIVE_FOLDER_ID_PATTERN = r"/folders/([a-zA-Z0-9_-]+)"

# Default Values
DEFAULT_THUMBNAIL = "https://via.placeholder.com/200x120?text=No+Thumb"

# Flash Message Categories
FLASH_SUCCESS = "success"
FLASH_DANGER = "danger"
FLASH_WARNING = "warning"
FLASH_INFO = "info"

# Database Query Fields
DRIVE_THUMBNAIL_FIELDS = "thumbnailLink"
DRIVE_FILE_FIELDS = "id, mimeType, webViewLink, shortcutDetails"
DRIVE_TARGET_FIELDS = "id, mimeType"

# MIME Types
MIME_SHORTCUT = "application/vnd.google-apps.shortcut"
MIME_FOLDER = "application/vnd.google-apps.folder"
MIME_IMAGE_PREFIX = "image/"

# To test Google authentication before deploying.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


### - Database Functions - ###
def save_backup(backup_name=None):
    # 1) Grab *all* rows from images, not just the first page
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, tags, thumbnail FROM images ORDER BY id")
    rows = c.fetchall()
    conn.close()

    # 2) Build your backup list from every row
    full_data = []
    for file_id, tags_json, thumb in rows:
        full_data.append({
            "id": file_id,
            "tags": json.loads(tags_json),
            "thumb_url": thumb
        })

    # 3) Store it as JSON in backups
    # Use custom name if provided, otherwise use timestamp
    if backup_name and backup_name.strip():
        timestamp = backup_name.strip()
    else:
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO backups (timestamp, data) VALUES (?, ?)",
              (timestamp, json.dumps(full_data)))
    conn.commit()
    conn.close()

def load_backup(backup_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT data FROM backups WHERE id = ?", (backup_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return False  # No backup found

    data = json.loads(row[0])

    # Clear current data
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM images")

    # Restore all items from backup (including thumbnail)
    for item in data:
        # Use .get('thumb_url') to handle possible missing keys safely
        thumbnail = item.get("thumb_url", None)
        c.execute(
            "INSERT INTO images (id, tags, thumbnail) VALUES (?, ?, ?)",
            (item["id"], json.dumps(item["tags"]), thumbnail)
        )

    conn.commit()
    conn.close()
    return True

def list_backups():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, timestamp FROM backups ORDER BY id DESC")
    backups = c.fetchall()
    conn.close()
    return backups

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Create images table with id, tags, and thumbnail (only once)
    c.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            tags TEXT,
            thumbnail TEXT
        )
    """)

    # Create backups table
    c.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            data TEXT
        )
    """)

    conn.commit()
    conn.close()


def load_data(page=DEFAULT_PAGE, per_page=ITEMS_PER_PAGE):
    offset = (page - 1) * per_page
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT id, tags, thumbnail
        FROM images
        ORDER BY id
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    rows = c.fetchall()
    conn.close()

    data = []
    for file_id, tag_str, thumb in rows:
        data.append({
            "id": file_id,
            "tags": json.loads(tag_str),
            "thumb_url": thumb or DEFAULT_THUMBNAIL
        })
    return data


    # Closes the connection and returns the fully loaded data list.
    conn.close()
    return data


def save_item(item_id, tags):
    # Attempt to get thumbnailLink from Google Drive (once per image)
    thumb = None
    if "credentials" in session:
        creds = Credentials(**session["credentials"])
        service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
        try:
            meta = service.files().get(
                fileId=item_id,
                fields=DRIVE_THUMBNAIL_FIELDS,
                supportsAllDrives=True
            ).execute()
            thumb = meta.get("thumbnailLink")
        except Exception as e:
            print(f"Thumbnail fetch failed for {item_id}: {e}")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    tags_json = json.dumps(tags)
    c.execute("""
        INSERT OR REPLACE INTO images (id, tags, thumbnail)
        VALUES (?, ?, ?)
    """, (item_id, tags_json, thumb))

    conn.commit()
    conn.close()


def delete_item(item_id):
    # Opens a connection to the database to remove a specific record.
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Deletes the image row with the matching ID from the "images" table.
    c.execute("DELETE FROM images WHERE id = ?", (item_id,))

    # Commits the changes, then closes the connection.
    conn.commit()
    conn.close()


### - Folder Checker - ###
def list_images_in_folder(folder_id, creds):
    # Creates a Google Drive API service instance using the provided credentials.
    service = googleapiclient.discovery.build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)

    # Defines a query to retrieve all non-trashed files and folders that are direct children of the specified folder ID.
    query = "'" + folder_id + "' in parents and trashed = false"

    # Executes the query, asking for essential fields and supporting shared drives (if enabled).
    results = service.files().list(
        q=query,
        fields=f"files({DRIVE_FILE_FIELDS})",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()

    # Retrieves the list of files and folders from the results dictionary.
    files = results.get("files", [])

    # Initializes an empty list to hold image IDs found in this folder and any subfolders.
    image_links = []

    # Iterates through each item in the folder to determine its type and decide how to process it.
    for f in files:
        file_id = f.get("id")
        mime = f.get("mimeType")

        # Checks if the file is a shortcut to another file.
        if mime == MIME_SHORTCUT:
            target_id = f.get("shortcutDetails", {}).get("targetId")

            # Attempts to resolve the shortcut to its target and include if it's an image.
            if target_id:
                try:
                    target = service.files().get(
                        fileId=target_id,
                        fields=DRIVE_TARGET_FIELDS,
                        supportsAllDrives=True
                    ).execute()
                except Exception:
                    continue

                target_mime = target.get("mimeType")

                if target_mime and target_mime.startswith(MIME_IMAGE_PREFIX):
                    image_links.append(target.get("id"))

        # Adds the file directly if it is an image (e.g., JPEG, PNG).
        elif mime and mime.startswith(MIME_IMAGE_PREFIX):
            image_links.append(f.get("id"))

        # Recursively processes folders by calling this function again with the subfolder's ID.
        elif mime == MIME_FOLDER:
            image_links.extend(list_images_in_folder(file_id, creds))

    # Returns a flat list containing all image IDs collected from this folder and its children.
    return image_links


### - Google Authentication - ###
@app.route("/authorize")
def authorize():
    # Initializes an OAuth flow from the "credentials.json" file using only read-only Drive access.
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=OAUTH_SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI
    )

    # Generates an authorization URL that users will visit to grant access and return a state token.
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true")

    # Stores the state in session so it can be verified later when Google redirects back.
    session["state"] = state

    return redirect(auth_url)


@app.route("/oauth2callback")
def oauth2callback():
    # Retrieves the state token from session to verify that this callback is legitimate.
    state = session["state"]

    # Sets up the OAuth flow again with the same scopes and redirect URI to complete token exchange.
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=OAUTH_SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI
    )

    # Exchanges the authorization response URL for a set of access tokens.
    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials

    # Stores credential details in the session so they can be reused for API calls.
    session["credentials"] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }

    return redirect("/")

def get_thumbnail_url(file_id, creds):
    service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
    try:
        file = service.files().get(
            fileId=file_id,
            fields=DRIVE_THUMBNAIL_FIELDS,
            supportsAllDrives=True
        ).execute()
        return file.get("thumbnailLink")
    except Exception as e:
        print(f"Error retrieving thumbnail for {file_id}: {e}")
        return None

### - Main Route - ###
@app.route("/", methods=["GET", "POST"])
def index():
    if "credentials" not in session:
        return redirect("/authorize")

    creds = Credentials(**session["credentials"])
    oauth2_service = build("oauth2", OAUTH2_API_VERSION, credentials=creds)
    user_info = oauth2_service.userinfo().get().execute()
    email = user_info.get("email")

    if email not in ALLOWED_USERS:
        return abort(403)

    page = int(request.args.get("page", DEFAULT_PAGE))
    per_page = ITEMS_PER_PAGE
    data = load_data(page=page, per_page=per_page)

    # Get all unique tags for filtering
    all_tags_set = set()
    for item in data:
        all_tags_set.update(item["tags"])
    all_tags = sorted(all_tags_set)

    # Search filtering (after load, before display)
    search_query = request.args.get("q", "").strip().lower()
    if search_query:
        terms = [q.strip() for q in search_query.split(",") if q.strip()]
        def matches_all(item):
            return all(
                term in item["id"].lower() or any(term in t for t in item["tags"])
                for term in terms
            )
        data = [item for item in data if matches_all(item)]

    # Handle POST: tagging or adding images
    if request.method == "POST":
        photo_id = request.form.get("photo_id")
        new_tag = request.form.get("tag", "").strip().lower()

        if photo_id and new_tag:
            tags_to_add = [t.strip() for t in new_tag.split(",") if t.strip()]
            for item in data:
                if item["id"] == photo_id:
                    for tag in tags_to_add:
                        if tag not in item["tags"]:
                            item["tags"].append(tag)
                    save_item(photo_id, item["tags"])
                    break
            return redirect("/")

        # Handle new uploads
        links = request.form.get("link", "").strip()
        tags_input = request.form.get("tag", "").strip().lower()
        link_list = [l.strip() for l in links.split(",") if l.strip()]
        tag_list = [t.strip() for t in tags_input.split(",") if t.strip()]

        if "credentials" in session:
            creds = Credentials(**session["credentials"])

        for link in link_list:
            match_file = re.search(DRIVE_FILE_ID_PATTERN, link)
            match_folder = re.search(DRIVE_FOLDER_ID_PATTERN, link)

            if match_file:
                file_id = match_file.group(1)
                exists = next((item for item in data if item["id"] == file_id), None)
                if exists:
                    for tag in tag_list:
                        if tag not in exists["tags"]:
                            exists["tags"].append(tag)
                    save_item(file_id, exists["tags"])
                else:
                    save_item(file_id, tag_list)

            elif match_folder:
                folder_id = match_folder.group(1)
                image_ids = list_images_in_folder(folder_id, creds)
                for file_id in image_ids:
                    exists = next((item for item in data if item["id"] == file_id), None)
                    if exists:
                        for tag in tag_list:
                            if tag not in exists["tags"]:
                                exists["tags"].append(tag)
                        save_item(file_id, exists["tags"])
                    else:
                        save_item(file_id, tag_list)

        return redirect("/")

    # Get total count for pagination
    conn = sqlite3.connect(DB_FILE)
    total_items = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    conn.close()
    total_pages = (total_items + per_page - 1) // per_page

    backups = list_backups()

    return render_template("index.html",
        data=data,
        all_tags=all_tags,
        backups=backups,
        page=page,
        total_pages=total_pages
    )


### - Remove Tag - ###
@app.route("/removetag", methods=["POST"])
def removetag():
    # Gets the image ID and tag name from the submitted form data.
    file_id = request.form["id"]
    tag = request.form["tag"]

    # Loads the current data from the database to update it.
    data = load_data()

    # Looks for the specific image and removes the specified tag if present.
    for item in data:
        if item["id"] == file_id and tag in item["tags"]:
            item["tags"].remove(tag)
            save_item(item["id"], item["tags"])
            break

    return redirect("/")


### - Remove Photo - ###
@app.route("/removephoto", methods=["POST"])
def remove():
    # Gets the image ID from the submitted form data to delete it.
    file_id = request.form["id"]

    # Removes the image from the database.
    delete_item(file_id)

    return redirect("/")

### - Edit Tag - ###
@app.route("/tag/edit", methods=["POST"])
def edit_tag():
    old_tag = request.form.get("old_tag", "").strip().lower()
    new_tag = request.form.get("new_tag", "").strip().lower()
    if not old_tag or not new_tag or old_tag == new_tag:
        flash("Invalid tag rename.", FLASH_DANGER)
        return redirect("/")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Fetch all images containing the old tag
    c.execute("SELECT id, tags FROM images")
    rows = c.fetchall()

    updated = 0
    for file_id, tags_json in rows:
        tags = json.loads(tags_json)
        if old_tag in tags:
            # Replace old_tag with new_tag
            tags = [new_tag if t == old_tag else t for t in tags]
            # Remove duplicates (in case new_tag already existed)
            tags = list(dict.fromkeys(tags))
            # Save back
            c.execute(
                "UPDATE images SET tags = ? WHERE id = ?",
                (json.dumps(tags), file_id)
            )
            updated += 1

    conn.commit()
    conn.close()

    flash(f"Renamed '{old_tag}' to '{new_tag}' on {updated} image(s).", FLASH_SUCCESS)
    return redirect("/")

### - Backup - ###
@app.route("/backup/save", methods=["POST"])
def backup_save():
    backup_name = request.form.get("backup_name", "").strip()
    save_backup(backup_name)

    if backup_name:
        flash(f"Backup '{backup_name}' saved successfully!")
    else:
        flash("Backup saved successfully!")
    return redirect("/")

@app.route("/backup/load/<int:backup_id>", methods=["POST"])
def backup_load(backup_id):
    success = load_backup(backup_id)
    if success:
        flash("Backup loaded successfully!")
    else:
        flash("Backup not found!", FLASH_DANGER)
    return redirect("/")

@app.route("/backup/delete/<int:backup_id>", methods=["POST"])
def backup_delete(backup_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
    conn.commit()
    conn.close()

    flash(f"Backup {backup_id} deleted.")
    return redirect("/")

### - Delete All - ###
@app.route("/delete/all", methods=["POST"])
def delete_all_photos():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM images")
    conn.commit()
    conn.close()
    flash("All photos and tags have been deleted.", FLASH_WARNING)
    return redirect("/")

### - Program Start - ###
if __name__ == "__main__":
    # Initializes the database (creates tables if needed) on startup.
    init_db()

    # Starts the Flask web server on all network interfaces at port 8080 so it can be accessed externally.
    app.run(host=SERVER_HOST, port=SERVER_PORT)