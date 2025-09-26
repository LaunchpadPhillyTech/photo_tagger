### - Libraries - ###
import dotenv
from flask import Flask, render_template, request, redirect, session, abort, flash
import os
import re
from dotenv import load_dotenv
import sqlite3
import json
import datetime

load_dotenv()  # Load environment variables from .env file

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.http import BatchHttpRequest
import googleapiclient.discovery
from googleapiclient.discovery import build


### - Flask App Setup - ###
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise ValueError("No FLASK_SECRET_KEY set for Flask application. Please set it in your .env file.")

# Add these session configurations
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


### - Configuration Constants - ###
# User Access Control
ALLOWED_USERS = {
    "aloped0091@launchpadphilly.org",
    "placeholder@launchpadphilly.org",
    "melanie@b-21.org", 
    "rob@launchpadphilly.org", 
    "christian@launchpadphilly.org"
}

# Database Configuration
DB_FILE = "data/data.db"

# Pagination Settings
DEFAULT_PAGE = 1
ITEMS_PER_PAGE = 40

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:3000/callback/oauth2callback")

if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_PROJECT_ID]):
    raise ValueError("Missing one or more GOOGLE_... OAuth environment variables. Please check your .env file.")

# This dictionary is used to configure the OAuth flow.
# It's constructed from environment variables instead of a JSON file.
client_config = {
    "web": {
        "project_id": GOOGLE_PROJECT_ID,
        "client_id": GOOGLE_CLIENT_ID,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": OAUTH_REDIRECT_URI,
    }
}

print(f"[OAuth Config] Client ID: {GOOGLE_CLIENT_ID}..., Redirect URI: {OAUTH_REDIRECT_URI}")

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

# Server Configuration
SERVER_HOST = "https://photo-tagger-app-npbtz.ondigitalocean.app/"
SERVER_PORT = int(os.getenv("PORT", 3000))

print(f"[Server Configuration] Running on {SERVER_HOST}:{SERVER_PORT}") 

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
    """
    Enhanced backup function that saves ALL data including current thumbnail status
    """
    # 1) Grab *all* rows from images, not just the first page
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, tags, thumbnail FROM images ORDER BY id")
    rows = c.fetchall()
    conn.close()

    # 2) Build your backup list from every row - preserve current thumbnail state
    full_data = []
    for file_id, tags_json, thumb in rows:
        # Store the actual thumbnail URL or None if invalid
        valid_thumb = thumb if is_valid_thumbnail(thumb) else None
        
        full_data.append({
            "id": file_id,
            "tags": json.loads(tags_json) if tags_json else [],
            "thumb_url": valid_thumb,
            "backup_timestamp": datetime.datetime.now().isoformat()
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

def is_valid_thumbnail(thumb):
    """
    Enhanced validation for thumbnail URLs.
    Returns True only for valid, non-expired Google Drive thumbnails.
    """
    if not thumb:
        return False
    if not isinstance(thumb, str):
        return False
    
    thumb = thumb.strip()
    if not thumb:
        return False
    
    # Must be a proper HTTP(S) URL
    if not (thumb.startswith("http://") or thumb.startswith("https://")):
        return False
    
    # Reject our default placeholder thumbnail
    if thumb == DEFAULT_THUMBNAIL:
        return False
    
    # UPDATED: Only reject OLD expired formats, not the new drive-storage URLs
    # Old expired patterns (these are truly expired)
    old_expired_patterns = [
        "lh3.googleusercontent.com/u/",  # Old user-specific URLs
        "lh4.googleusercontent.com/u/",
        "lh5.googleusercontent.com/u/",
        "lh6.googleusercontent.com/u/",
        # Add other old patterns that are definitely expired
    ]
    
    for pattern in old_expired_patterns:
        if pattern in thumb:
            return False
    
    # ACCEPT the new drive-storage format - these are VALID
    if "lh3.googleusercontent.com/drive-storage/" in thumb:
        return True
    if "lh4.googleusercontent.com/drive-storage/" in thumb:
        return True
    if "lh5.googleusercontent.com/drive-storage/" in thumb:
        return True
    if "lh6.googleusercontent.com/drive-storage/" in thumb:
        return True
    
    # Reject obvious broken/expired indicators in URL
    invalid_tokens = [
        "expired", "null", "notfound", "deleted", "unavailable", 
        "error", "invalid", "broken", "404", "403"
    ]
    
    lower_thumb = thumb.lower()
    for token in invalid_tokens:
        if token in lower_thumb:
            return False
    
    # Additional check: reject very short URLs (likely broken)
    if len(thumb) < 20:
        return False
    
    # Accept other valid Google domains
    valid_domains = [
        "drive.google.com", 
        "drive.usercontent.google.com",
        "googleusercontent.com"  # Accept all googleusercontent.com domains
    ]
    
    has_valid_domain = any(domain in thumb for domain in valid_domains)
    return has_valid_domain


def is_expired_thumbnail(thumb):
    """
    Separate function to check if a thumbnail should be considered expired.
    This is more conservative - only flags truly old/broken URLs for refresh.
    """
    if not thumb:
        return True
    
    # These are the OLD patterns that should definitely be refreshed
    truly_expired_patterns = [
        "lh3.googleusercontent.com/u/",  # Old user-specific format
        "lh4.googleusercontent.com/u/",
        "lh5.googleusercontent.com/u/",
        "lh6.googleusercontent.com/u/",
        "photos.google.com",  # Very old format
    ]
    
    for pattern in truly_expired_patterns:
        if pattern in thumb:
            return True
    
    # Default placeholder should be refreshed
    if thumb == DEFAULT_THUMBNAIL:
        return True
        
    return False


def force_refresh_backup_thumbnails(backup_id, creds):
    """
    Utility function to force refresh all thumbnails for a specific backup
    Can be called after loading a backup if thumbnails are still problematic
    """
    if not creds:
        return False, "No credentials available"
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get the backup data to know which files to refresh
    c.execute("SELECT data FROM backups WHERE id = ?", (backup_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Backup not found"
    
    try:
        data = json.loads(row[0])
        file_ids = [item.get("id") for item in data if item.get("id")]
    except Exception as e:
        conn.close()
        return False, f"Backup data corrupted: {str(e)}"
    
    if not file_ids:
        conn.close()
        return False, "No files found in backup"
    
    try:
        service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
        
        success_count = 0
        fail_count = 0
        
        # Process files individually for better error handling
        for file_id in file_ids:
            try:
                file_metadata = service.files().get(
                    fileId=file_id,
                    fields=DRIVE_THUMBNAIL_FIELDS,
                    supportsAllDrives=True
                ).execute()
                
                new_thumbnail = file_metadata.get("thumbnailLink")
                if new_thumbnail and is_valid_thumbnail(new_thumbnail):
                    c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (new_thumbnail, file_id))
                    success_count += 1
                else:
                    c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
                    fail_count += 1
                    
            except Exception as e:
                print(f"[force_refresh_backup_thumbnails] failed for {file_id}: {e}")
                c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
                fail_count += 1
            
            # Small delay to avoid hitting rate limits
            import time
            time.sleep(0.1)
        
        conn.commit()
        conn.close()
        
        return True, f"Processed {len(file_ids)} files: {success_count} successful, {fail_count} failed"
        
    except Exception as e:
        conn.close()
        return False, f"Error during refresh: {str(e)}"

def load_backup(backup_id, creds=None, try_refresh_missing=True):
    """
    Enhanced backup loading with robust thumbnail handling
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT data FROM backups WHERE id = ?", (backup_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "Backup not found"

    try:
        data = json.loads(row[0])
    except Exception as e:
        print(f"[load_backup] malformed backup JSON for id {backup_id}: {e}")
        conn.close()
        return False, f"Backup data corrupted: {str(e)}"

    restored_count = 0
    thumbnail_refresh_needed = []
    
    # Process each item in the backup
    for item in data:
        file_id = item.get("id")
        if not file_id:
            continue
            
        backup_tags = item.get("tags", [])
        backup_thumb = item.get("thumb_url")

        # Check if this file already exists in current database
        c.execute("SELECT tags, thumbnail FROM images WHERE id = ?", (file_id,))
        existing = c.fetchone()

        # Determine the best thumbnail to use
        chosen_thumb = None
        needs_refresh = False
        
        if existing:
            existing_tags_json, existing_thumb = existing
            
            # Priority: existing valid thumbnail > backup thumbnail > refresh needed
            if is_valid_thumbnail(existing_thumb):
                chosen_thumb = existing_thumb
            elif is_valid_thumbnail(backup_thumb):
                chosen_thumb = backup_thumb
            else:
                chosen_thumb = None
                needs_refresh = True
            
            # Update with backup tags (restore backup state)
            c.execute(
                "UPDATE images SET tags = ?, thumbnail = ? WHERE id = ?",
                (json.dumps(backup_tags), chosen_thumb, file_id)
            )
            
        else:
            # New file from backup
            if is_valid_thumbnail(backup_thumb):
                chosen_thumb = backup_thumb
            else:
                chosen_thumb = None
                needs_refresh = True
                
            c.execute(
                "INSERT INTO images (id, tags, thumbnail) VALUES (?, ?, ?)",
                (file_id, json.dumps(backup_tags), chosen_thumb)
            )
        
        restored_count += 1
        
        # Track files that need thumbnail refresh
        if needs_refresh:
            thumbnail_refresh_needed.append(file_id)

    conn.commit()

    # Attempt to refresh thumbnails for files that need it
    refreshed_count = 0
    failed_count = len(thumbnail_refresh_needed)
    
    if thumbnail_refresh_needed and try_refresh_missing and creds:
        print(f"[load_backup] refreshing thumbnails for {len(thumbnail_refresh_needed)} items...")
        
        try:
            service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
            
            # Process in smaller batches to avoid timeouts
            batch_size = 20
            for i in range(0, len(thumbnail_refresh_needed), batch_size):
                batch_files = thumbnail_refresh_needed[i:i + batch_size]
                
                # Use individual requests for better error handling
                for file_id in batch_files:
                    try:
                        file_metadata = service.files().get(
                            fileId=file_id,
                            fields=DRIVE_THUMBNAIL_FIELDS,
                            supportsAllDrives=True
                        ).execute()
                        
                        new_thumbnail = file_metadata.get("thumbnailLink")
                        if new_thumbnail and is_valid_thumbnail(new_thumbnail):
                            c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (new_thumbnail, file_id))
                            refreshed_count += 1
                            failed_count -= 1
                        else:
                            # Set to default placeholder if no valid thumbnail available
                            c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
                            
                    except Exception as e:
                        print(f"[load_backup] thumbnail refresh failed for {file_id}: {e}")
                        # Set to default placeholder on error
                        c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
                
                conn.commit()
                
                # Small delay between batches
                import time
                time.sleep(0.5)
                        
        except Exception as e:
            print(f"[load_backup] batch thumbnail refresh error: {e}")
            # Set all remaining files to default placeholder
            for file_id in thumbnail_refresh_needed:
                c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
            conn.commit()

    conn.close()
    
    # Prepare success message
    message_parts = [f"Restored {restored_count} photos"]
    if refreshed_count > 0:
        message_parts.append(f"refreshed {refreshed_count} thumbnails")
    if failed_count > 0:
        message_parts.append(f"{failed_count} thumbnails need manual refresh")
    
    success_message = ", ".join(message_parts)
    return True, success_message

def list_backups():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, timestamp FROM backups ORDER BY id DESC")
    backups = c.fetchall()
    conn.close()
    return backups

def init_db():
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    
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

    data = []
    expired_files = {}

    for file_id, tag_str, thumb in rows:
        # Use the new expired check function - only refresh truly old/broken URLs
        if not thumb or is_expired_thumbnail(thumb):
            expired_files[file_id] = tag_str
        else:
            data.append({
                "id": file_id,
                "tags": json.loads(tag_str),
                "thumb_url": thumb
            })

    # Only attempt to refresh thumbnails if we have expired files AND credentials
    if expired_files and "credentials" in session:
        creds = Credentials(**session["credentials"])
        service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
        
        # First, clear all expired thumbnails from database
        expired_ids = list(expired_files.keys())
        placeholders = ','.join(['?' for _ in expired_ids])
        c.execute(f"UPDATE images SET thumbnail = NULL WHERE id IN ({placeholders})", expired_ids)
        conn.commit()
        
        batch = BatchHttpRequest(batch_uri='https://www.googleapis.com/batch/drive/v3')
        refreshed_thumbnails = {}

        def callback(request_id, response, exception):
            if exception:
                print(f"Thumbnail fetch failed for {request_id}: {exception}")
                refreshed_thumbnails[request_id] = DEFAULT_THUMBNAIL
                return
            
            new_thumbnail = response.get("thumbnailLink")
            if new_thumbnail and is_valid_thumbnail(new_thumbnail):
                refreshed_thumbnails[request_id] = new_thumbnail
            else:
                refreshed_thumbnails[request_id] = DEFAULT_THUMBNAIL

        for file_id in expired_files.keys():
            batch.add(
                service.files().get(
                    fileId=file_id,
                    fields=DRIVE_THUMBNAIL_FIELDS,
                    supportsAllDrives=True
                ),
                request_id=file_id,
                callback=callback
            )

        try:
            batch.execute()  # Execute the batch request
            
            # After batch finishes, update DB with completely new thumbnails
            for file_id, tag_str in expired_files.items():
                new_thumb_url = refreshed_thumbnails.get(file_id, DEFAULT_THUMBNAIL)
                
                # Add the item to data with refreshed thumbnail
                data.append({
                    "id": file_id,
                    "tags": json.loads(tag_str),
                    "thumb_url": new_thumb_url
                })
                
                # Update the database with the completely new thumbnail
                c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (new_thumb_url, file_id))
                
        except Exception as e:
            print(f"Batch execution failed: {e}")
            # Fallback: add expired files with default thumbnail and clear DB thumbnails
            for file_id, tag_str in expired_files.items():
                data.append({
                    "id": file_id,
                    "tags": json.loads(tag_str),
                    "thumb_url": DEFAULT_THUMBNAIL
                })
                # Set to DEFAULT_THUMBNAIL instead of leaving null
                c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
    else:
        # If no credentials or no expired files, add expired files with default thumbnail
        for file_id, tag_str in expired_files.items():
            data.append({
                "id": file_id,
                "tags": json.loads(tag_str),
                "thumb_url": DEFAULT_THUMBNAIL
            })
            # Clear the expired thumbnail from database
            c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))

    conn.commit()
    conn.close()

    return data

# def load_data(page=DEFAULT_PAGE, per_page=ITEMS_PER_PAGE):
#     offset = (page - 1) * per_page
#     conn = sqlite3.connect(DB_FILE)
#     c = conn.cursor()

#     c.execute("""
#         SELECT id, tags, thumbnail
#         FROM images
#         ORDER BY id
#         LIMIT ? OFFSET ?
#     """, (per_page, offset))
#     rows = c.fetchall()
#     conn.close()

#     data = []
#     for file_id, tag_str, thumb in rows:
#         data.append({
#             "id": file_id,
#             "tags": json.loads(tag_str),
#             "thumb_url": thumb or DEFAULT_THUMBNAIL
#         })

#     # Closes the connection and returns the fully loaded data list.
#     conn.close()
#     return data


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

    # Initializes an OAuth flow from the client_config dictionary.
    flow = Flow.from_client_config(
        client_config,
        scopes=OAUTH_SCOPES,
        redirect_uri=OAUTH_REDIRECT_URI
    )

    # Generates an authorization URL that users will visit to grant access and return a state token.
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")

    # Stores the state in session so it can be verified later when Google redirects back.
    session["state"] = state

    return redirect(auth_url)


@app.route("/callback/oauth2callback")
def oauth2callback():
    # Check if state exists in session
    if "state" not in session:
        flash("Authentication session expired. Please try again.", FLASH_WARNING)
        return redirect("/authorize")
    
    # Retrieves the state token from session to verify that this callback is legitimate.
    state = session["state"]

    print("[OAuth2 Callback] State:", state)
    print("[OAuth2 Callback] Request URL:", request.url)
    print("[OAuth2 Callback] Request args:", request.args)

    # Sets up the OAuth flow again with the same config to complete token exchange.
    flow = Flow.from_client_config(
        client_config,
        scopes=OAUTH_SCOPES,
        state=state,
        redirect_uri=OAUTH_REDIRECT_URI
    )

    try:
        # Exchanges the authorization response URL for a set of access tokens.
        token = flow.fetch_token(authorization_response=request.url)
        
        creds = flow.credentials

        # print(f"[OAuth2 Callback] Token fetched successfully: {token}")
        # print(f"[OAuth2 Callback] Credentials: {creds}")
        # print(f"[OAuth2 Callback] Scopes: {creds.scopes}")  

        session["credentials"] = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes
        }
        
        # Clean up the state from session
        session.pop("state", None)
        
        flash("Successfully authenticated!", FLASH_SUCCESS)
        return redirect("/")
        
    except Exception as e:
        import traceback
        print(f"[OAuth2 Callback] Error type: {type(e).__name__}")
        print(f"[OAuth2 Callback] Error message: {e}")
        print(f"[OAuth2 Callback] Request URL: {request.url}")
        print(f"[OAuth2 Callback] Request args: {request.args}")
        print(f"[OAuth2 Callback] Flow state: {getattr(flow, 'state', 'No state')}")
        print(f"[OAuth2 Callback] Session state: {session.get('state', 'No state')}")
        print(f"[OAuth2 Callback] Traceback: {traceback.format_exc()}")
        flash(f"Authentication failed: {str(e)}", FLASH_DANGER)
        return redirect("/authorize")

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
        print("No credentials found in session, redirecting to authorize.")
        return redirect("/authorize")

    creds = Credentials(**session["credentials"])
    oauth2_service = build("oauth2", OAUTH2_API_VERSION, credentials=creds)
    user_info = oauth2_service.userinfo().get().execute()
    email = user_info.get("email")

    if email not in ALLOWED_USERS:
        return abort(403, description="You are not authorized to access this application.")

    # Handle POST requests first (tagging, adding images, etc.)
    if request.method == "POST":
        photo_id = request.form.get("photo_id")
        new_tag = request.form.get("tag", "").strip().lower()

        if photo_id and new_tag:
            # Handle individual photo tagging
            tags_to_add = [t.strip() for t in new_tag.split(",") if t.strip()]
            
            # Get current tags for this photo from database
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT tags FROM images WHERE id = ?", (photo_id,))
            result = c.fetchone()
            conn.close()
            
            if result:
                current_tags = json.loads(result[0])
                for tag in tags_to_add:
                    if tag not in current_tags:
                        current_tags.append(tag)
                save_item(photo_id, current_tags)
            
            return redirect(f"/?{request.query_string.decode()}")  # Preserve search/page params

        # Handle new uploads (files/folders)
        links = request.form.get("link", "").strip()
        tags_input = request.form.get("tag", "").strip().lower()
        link_list = [l.strip() for l in links.split(",") if l.strip()]
        tag_list = [t.strip() for t in tags_input.split(",") if t.strip()]

        for link in link_list:
            match_file = re.search(DRIVE_FILE_ID_PATTERN, link)
            match_folder = re.search(DRIVE_FOLDER_ID_PATTERN, link)

            if match_file:
                file_id = match_file.group(1)
                # Check if file already exists
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT tags FROM images WHERE id = ?", (file_id,))
                existing = c.fetchone()
                conn.close()
                
                if existing:
                    existing_tags = json.loads(existing[0])
                    for tag in tag_list:
                        if tag not in existing_tags:
                            existing_tags.append(tag)
                    save_item(file_id, existing_tags)
                else:
                    save_item(file_id, tag_list)

            elif match_folder:
                folder_id = match_folder.group(1)
                image_ids = list_images_in_folder(folder_id, creds)
                for file_id in image_ids:
                    # Check if file already exists  
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("SELECT tags FROM images WHERE id = ?", (file_id,))
                    existing = c.fetchone()
                    conn.close()
                    
                    if existing:
                        existing_tags = json.loads(existing[0])
                        for tag in tag_list:
                            if tag not in existing_tags:
                                existing_tags.append(tag)
                        save_item(file_id, existing_tags)
                    else:
                        save_item(file_id, tag_list)

        return redirect("/")

    # GET request handling - Load and display data
    page = int(request.args.get("page", DEFAULT_PAGE))
    per_page = ITEMS_PER_PAGE
    search_query = request.args.get("q", "").strip().lower()

    # Get total count and filtered count for proper pagination
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    if search_query:
        # If searching, we need to handle this differently
        # Get ALL data first, then filter, then paginate
        c.execute("SELECT id, tags, thumbnail FROM images ORDER BY id")
        all_rows = c.fetchall()
        
        # Build the full dataset
        all_data = []
        expired_files = {}
        
        for file_id, tag_str, thumb in all_rows:
            if not thumb or is_expired_thumbnail(thumb):
                expired_files[file_id] = tag_str
            else:
                all_data.append({
                    "id": file_id,
                    "tags": json.loads(tag_str),
                    "thumb_url": thumb
                })
        
        # Add expired files with placeholder thumbnails for now
        for file_id, tag_str in expired_files.items():
            all_data.append({
                "id": file_id,
                "tags": json.loads(tag_str),
                "thumb_url": DEFAULT_THUMBNAIL
            })
        
        # Apply search filter
        terms = [q.strip() for q in search_query.split(",") if q.strip()]
        def matches_all(item):
            return all(
                term in item["id"].lower() or any(term in t.lower() for t in item["tags"])
                for term in terms
            )
        
        filtered_data = [item for item in all_data if matches_all(item)]
        
        # Calculate pagination for filtered results
        total_filtered = len(filtered_data)
        total_pages = (total_filtered + per_page - 1) // per_page if total_filtered > 0 else 1
        
        # Apply pagination to filtered results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        data = filtered_data[start_idx:end_idx]
        
        # Now refresh expired thumbnails for the current page only
        page_expired_files = {}
        for item in data:
            if item["thumb_url"] == DEFAULT_THUMBNAIL:
                # Find the original tag string for this file
                for fid, tag_str in expired_files.items():
                    if fid == item["id"]:
                        page_expired_files[fid] = tag_str
                        break
        
        # Refresh thumbnails for current page
        if page_expired_files and "credentials" in session:
            refresh_thumbnails_batch(page_expired_files, data, creds)
    
    else:
        # No search - use normal pagination
        total_items = c.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 1
        
        # Load page data normally
        data = load_data(page=page, per_page=per_page)
    
    conn.close()

    # Get all unique tags for the tag dropdown
    all_tags_set = set()
    if search_query:
        # For search results, only show tags from visible results
        for item in data:
            all_tags_set.update(item["tags"])
    else:
        # For normal view, show all tags in database
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT tags FROM images")
        for row in c.fetchall():
            if row[0]:  # Check if tags is not None
                tags = json.loads(row[0])
                all_tags_set.update(tags)
        conn.close()
    
    all_tags = sorted(all_tags_set)

    # Load backups list
    backups = list_backups()

    return render_template("index.html",
        data=data,
        all_tags=all_tags,
        backups=backups,
        page=page,
        total_pages=total_pages,
        search_query=search_query
    )

def refresh_thumbnails_batch(expired_files, data, creds):
    """Helper function to refresh thumbnails for a batch of files"""
    if not expired_files or not creds:
        return
        
    try:
        service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
        batch = BatchHttpRequest(batch_uri='https://www.googleapis.com/batch/drive/v3')
        refreshed_thumbnails = {}

        def callback(request_id, response, exception):
            if exception:
                print(f"Thumbnail fetch failed for {request_id}: {exception}")
                refreshed_thumbnails[request_id] = DEFAULT_THUMBNAIL
                return
            
            new_thumbnail = response.get("thumbnailLink")
            if new_thumbnail and is_valid_thumbnail(new_thumbnail):
                refreshed_thumbnails[request_id] = new_thumbnail
            else:
                refreshed_thumbnails[request_id] = DEFAULT_THUMBNAIL

        for file_id in expired_files.keys():
            batch.add(
                service.files().get(
                    fileId=file_id,
                    fields=DRIVE_THUMBNAIL_FIELDS,
                    supportsAllDrives=True
                ),
                request_id=file_id,
                callback=callback
            )

        batch.execute()
        
        # Update both the data list and the database
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        for item in data:
            if item["id"] in refreshed_thumbnails:
                new_thumb = refreshed_thumbnails[item["id"]]
                item["thumb_url"] = new_thumb
                c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (new_thumb, item["id"]))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Batch thumbnail refresh failed: {e}")
        # Fallback: just use default thumbnails
        for item in data:
            if item["thumb_url"] == DEFAULT_THUMBNAIL:
                pass  # Already set to default


### - Remove Tag - ###
@app.route("/removetag", methods=["POST"])
def removetag():
    # Gets the image ID and tag name from the submitted form data.
    file_id = request.form["id"]
    tag = request.form["tag"]
    return_url = request.form.get("return_url", "/")

    # Load the current tags from database and remove the specified tag
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT tags FROM images WHERE id = ?", (file_id,))
    result = c.fetchone()
    
    if result:
        current_tags = json.loads(result[0])
        if tag in current_tags:
            current_tags.remove(tag)
            save_item(file_id, current_tags)
    
    conn.close()
    return redirect(return_url)


### - Remove Photo - ###
@app.route("/removephoto", methods=["POST"])
def remove():
    # Gets the image ID from the submitted form data to delete it.
    file_id = request.form["id"]
    return_url = request.form.get("return_url", "/")

    # Removes the image from the database.
    delete_item(file_id)

    return redirect(return_url)

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
    try:
        save_backup(backup_name)
        if backup_name:
            flash(f"Backup '{backup_name}' saved successfully!", FLASH_SUCCESS)
        else:
            flash("Backup saved successfully!", FLASH_SUCCESS)
    except Exception as e:
        flash(f"Backup failed: {str(e)}", FLASH_DANGER)
    return redirect("/")

@app.route("/backup/load/<int:backup_id>", methods=["POST"])
def backup_load(backup_id):
    creds = None
    if "credentials" in session:
        try:
            creds = Credentials(**session["credentials"])
        except Exception as e:
            flash(f"Authentication error: {str(e)}", FLASH_WARNING)
            creds = None

    success, message = load_backup(backup_id, creds=creds, try_refresh_missing=True)
    
    if success:
        flash(f"Backup loaded: {message}", FLASH_SUCCESS)
    else:
        flash(f"Backup load failed: {message}", FLASH_DANGER)
    
    return redirect("/")

@app.route("/backup/delete/<int:backup_id>", methods=["POST"])
def backup_delete(backup_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get backup info before deleting for the flash message
    c.execute("SELECT timestamp FROM backups WHERE id = ?", (backup_id,))
    backup_info = c.fetchone()
    
    c.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
    deleted_rows = c.rowcount
    conn.commit()
    conn.close()

    if deleted_rows > 0:
        backup_name = backup_info[0] if backup_info else f"#{backup_id}"
        flash(f"Backup '{backup_name}' deleted successfully.", FLASH_INFO)
    else:
        flash(f"Backup {backup_id} not found.", FLASH_WARNING)
    
    return redirect("/")

@app.route("/backup/refresh/<int:backup_id>", methods=["POST"])
def backup_refresh_thumbnails(backup_id):
    """New route to force refresh thumbnails for a specific backup after loading"""
    if "credentials" not in session:
        flash("Please authenticate first.", FLASH_DANGER)
        return redirect("/authorize")
    
    try:
        creds = Credentials(**session["credentials"])
        success, message = force_refresh_backup_thumbnails(backup_id, creds)
        
        if success:
            flash(f"Thumbnail refresh completed: {message}", FLASH_SUCCESS)
        else:
            flash(f"Thumbnail refresh failed: {message}", FLASH_DANGER)
            
    except Exception as e:
        flash(f"Error during thumbnail refresh: {str(e)}", FLASH_DANGER)
    
    return redirect("/")

### - Delete All - ###
@app.route("/delete/all", methods=["POST"])
def delete_all_photos():
    """Enhanced delete all that properly cleans up everything"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get count before deleting for flash message
    c.execute("SELECT COUNT(*) FROM images")
    count = c.fetchone()[0]
    
    # Delete all images
    c.execute("DELETE FROM images")
    conn.commit()
    conn.close()
    
    flash(f"Deleted {count} photos and all their tags.", FLASH_WARNING)
    return redirect("/")

### - Thumbnail Refresh - ###
@app.route("/refresh/thumbnails", methods=["POST"])
def refresh_thumbnails():
    if "credentials" not in session:
        flash("Please authenticate first.", FLASH_DANGER)
        return redirect("/authorize")
    
    try:
        creds = Credentials(**session["credentials"])
        
        # Test credentials first
        oauth2_service = build("oauth2", OAUTH2_API_VERSION, credentials=creds)
        user_info = oauth2_service.userinfo().get().execute()
        print(f"[DEBUG] Authenticated as: {user_info.get('email')}")
        
        service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
        
        # Test basic Drive API access
        about = service.about().get(fields="user").execute()
        print(f"[DEBUG] Drive API access confirmed for user: {about.get('user', {}).get('emailAddress')}")
        
    except Exception as e:
        print(f"[DEBUG] Authentication/API test failed: {e}")
        flash(f"Authentication error: {str(e)}", FLASH_DANGER)
        return redirect("/authorize")
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get a small sample first for testing (limit to 5 files)
    test_mode = request.form.get("test_mode") == "true"
    if test_mode:
        c.execute("SELECT id FROM images LIMIT 5")
        flash("Running in test mode (5 files only)", FLASH_INFO)
    else:
        c.execute("SELECT id FROM images")
    
    all_files = [row[0] for row in c.fetchall()]
    
    if not all_files:
        flash("No files found to refresh.", FLASH_INFO)
        return redirect("/")
    
    print(f"[DEBUG] Found {len(all_files)} files to process")
    print(f"[DEBUG] Sample file IDs: {all_files[:3]}")
    
    # STEP 1: Clear existing thumbnails
    if not test_mode:
        c.execute("UPDATE images SET thumbnail = NULL")
        conn.commit()
    
    refreshed_count = 0
    failed_count = 0
    error_details = {}
    
    # STEP 2: Process in very small batches for debugging
    batch_size = 3 if test_mode else 10  # Smaller batches for better error tracking
    
    for i in range(0, len(all_files), batch_size):
        batch_files = all_files[i:i + batch_size]
        print(f"[DEBUG] Processing batch {i//batch_size + 1}: {batch_files}")
        
        # Try individual requests first instead of batch for better error tracking
        for file_id in batch_files:
            try:
                print(f"[DEBUG] Fetching thumbnail for file: {file_id}")
                
                # Single request with detailed error handling
                file_metadata = service.files().get(
                    fileId=file_id,
                    fields="id,name,mimeType,thumbnailLink,trashed,parents",
                    supportsAllDrives=True
                ).execute()
                
                print(f"[DEBUG] File metadata for {file_id}:")
                print(f"  - Name: {file_metadata.get('name', 'Unknown')}")
                print(f"  - MimeType: {file_metadata.get('mimeType', 'Unknown')}")
                print(f"  - Trashed: {file_metadata.get('trashed', False)}")
                print(f"  - Has thumbnail: {'thumbnailLink' in file_metadata}")
                
                thumbnail_url = file_metadata.get("thumbnailLink")
                
                if thumbnail_url:
                    print(f"[DEBUG] Got thumbnail URL: {thumbnail_url[:100]}...")
                    
                    if is_valid_thumbnail(thumbnail_url):
                        c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (thumbnail_url, file_id))
                        refreshed_count += 1
                        print(f"[DEBUG] ✓ Updated thumbnail for {file_id}")
                    else:
                        print(f"[DEBUG] ✗ Invalid thumbnail URL for {file_id}")
                        c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
                        failed_count += 1
                        error_details[file_id] = "Invalid thumbnail URL"
                else:
                    print(f"[DEBUG] ✗ No thumbnail available for {file_id}")
                    c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
                    failed_count += 1
                    error_details[file_id] = "No thumbnail in response"
                
            except Exception as e:
                print(f"[DEBUG] ✗ Error processing {file_id}: {e}")
                c.execute("UPDATE images SET thumbnail = ? WHERE id = ?", (DEFAULT_THUMBNAIL, file_id))
                failed_count += 1
                error_details[file_id] = str(e)
        
        conn.commit()  # Commit after each batch
        
        # Small delay to avoid hitting rate limits
        import time
        time.sleep(0.5)
    
    conn.close()
    
    # Print detailed error summary
    print(f"[DEBUG] Final results:")
    print(f"  - Successful: {refreshed_count}")
    print(f"  - Failed: {failed_count}")
    print(f"  - Error breakdown:")
    
    error_summary = {}
    for file_id, error in error_details.items():
        error_type = error.split(':')[0] if ':' in error else error
        error_summary[error_type] = error_summary.get(error_type, 0) + 1
    
    for error_type, count in error_summary.items():
        print(f"    - {error_type}: {count} files")
    
    # Create detailed flash message
    total_files = len(all_files)
    if refreshed_count > 0:
        message = f"Refreshed {refreshed_count}/{total_files} thumbnails successfully."
        if failed_count > 0:
            top_errors = sorted(error_summary.items(), key=lambda x: x[1], reverse=True)[:3]
            error_text = ", ".join([f"{err}: {count}" for err, count in top_errors])
            message += f" Failures: {error_text}"
        flash(message, FLASH_SUCCESS if refreshed_count > failed_count else FLASH_WARNING)
    else:
        top_errors = sorted(error_summary.items(), key=lambda x: x[1], reverse=True)[:2]
        error_text = ", ".join([f"{err}: {count}" for err, count in top_errors])
        flash(f"All {total_files} thumbnails failed. Main issues: {error_text}", FLASH_DANGER)
    
    return redirect("/")

@app.route("/clear/thumbnails", methods=["POST"])
def clear_all_thumbnails():
    """Route to completely clear all thumbnails without refreshing"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Clear ALL thumbnails
    c.execute("UPDATE images SET thumbnail = NULL")
    affected_rows = c.rowcount
    conn.commit()
    conn.close()
    
    flash(f"Cleared all thumbnails for {affected_rows} images. Use 'Refresh All Thumbnails' to regenerate them.", FLASH_INFO)
    return redirect("/")

@app.route("/test/single/<file_id>", methods=["POST"])
def test_single_thumbnail(file_id):
    """Test thumbnail fetch for a single file with full debugging"""
    if "credentials" not in session:
        flash("Please authenticate first.", FLASH_DANGER)
        return redirect("/authorize")
    
    try:
        creds = Credentials(**session["credentials"])
        service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
        
        print(f"[SINGLE TEST] Testing file: {file_id}")
        
        # Get full file metadata
        file_metadata = service.files().get(
            fileId=file_id,
            fields="*",  # Get all fields for debugging
            supportsAllDrives=True
        ).execute()
        
        print(f"[SINGLE TEST] Full metadata:")
        for key, value in file_metadata.items():
            if key != 'thumbnailLink' or len(str(value)) < 200:
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: {str(value)[:100]}...")
        
        thumbnail_url = file_metadata.get("thumbnailLink")
        
        if thumbnail_url:
            valid = is_valid_thumbnail(thumbnail_url)
            flash(f"File {file_id}: Found thumbnail ({'valid' if valid else 'invalid'}). URL: {thumbnail_url[:100]}...", FLASH_INFO)
        else:
            flash(f"File {file_id}: No thumbnail available. File type: {file_metadata.get('mimeType')}", FLASH_WARNING)
        
    except Exception as e:
        flash(f"Error testing file {file_id}: {str(e)}", FLASH_DANGER)
        print(f"[SINGLE TEST] Error: {e}")
    
    return redirect("/")

@app.route("/diagnostics", methods=["GET", "POST"])
def diagnostics():
    """Comprehensive diagnostics for thumbnail issues"""
    if "credentials" not in session:
        flash("Please authenticate first.", FLASH_DANGER)
        return redirect("/authorize")
    
    results = []
    
    try:
        # Test 1: Basic authentication
        creds = Credentials(**session["credentials"])
        results.append("✓ Credentials loaded successfully")
        
        # Test 2: OAuth2 API access
        oauth2_service = build("oauth2", OAUTH2_API_VERSION, credentials=creds)
        user_info = oauth2_service.userinfo().get().execute()
        results.append(f"✓ OAuth2 API: Authenticated as {user_info.get('email')}")
        
        # Test 3: Drive API access
        service = build("drive", GOOGLE_DRIVE_API_VERSION, credentials=creds)
        about = service.about().get(fields="user,storageQuota").execute()
        results.append(f"✓ Drive API: Access confirmed")
        
        # Test 4: Check database
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM images")
        total_images = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM images WHERE thumbnail IS NOT NULL AND thumbnail != ''")
        with_thumbnails = c.fetchone()[0]
        
        c.execute("SELECT id FROM images LIMIT 1")
        sample_file = c.fetchone()
        conn.close()
        
        results.append(f"✓ Database: {total_images} total images, {with_thumbnails} have thumbnails")
        
        if sample_file:
            file_id = sample_file[0]
            results.append(f"✓ Sample file ID: {file_id}")
            
            # Test 5: Try to fetch one file's metadata
            try:
                file_metadata = service.files().get(
                    fileId=file_id,
                    fields="id,name,mimeType,thumbnailLink,trashed,parents,capabilities",
                    supportsAllDrives=True
                ).execute()
                
                results.append(f"✓ Sample file metadata retrieved:")
                results.append(f"  - Name: {file_metadata.get('name', 'Unknown')}")
                results.append(f"  - Type: {file_metadata.get('mimeType', 'Unknown')}")
                results.append(f"  - Trashed: {file_metadata.get('trashed', 'Unknown')}")
                results.append(f"  - Has thumbnail: {'thumbnailLink' in file_metadata}")
                
                if 'thumbnailLink' in file_metadata:
                    thumb_url = file_metadata['thumbnailLink']
                    results.append(f"  - Thumbnail URL: {thumb_url[:80]}...")
                    results.append(f"  - URL valid: {is_valid_thumbnail(thumb_url)}")
                else:
                    results.append(f"  - No thumbnail available for this file type")
                
                # Check file capabilities
                caps = file_metadata.get('capabilities', {})
                results.append(f"  - Can read: {caps.get('canDownload', 'Unknown')}")
                results.append(f"  - Can view: {caps.get('canReadRevisions', 'Unknown')}")
                
            except Exception as e:
                results.append(f"✗ Error fetching sample file: {str(e)}")
                
                # If individual file fails, try a different approach
                try:
                    # Test with a simple files.list call
                    list_result = service.files().list(
                        pageSize=1,
                        fields="files(id,name,mimeType)",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True
                    ).execute()
                    
                    if list_result.get('files'):
                        results.append(f"✓ Files.list works - found accessible files")
                        test_file = list_result['files'][0]
                        results.append(f"  - Test file: {test_file.get('name')} ({test_file.get('id')})")
                    else:
                        results.append(f"✗ Files.list returned no results")
                        
                except Exception as e2:
                    results.append(f"✗ Files.list also failed: {str(e2)}")
        
        # Test 6: Check quota
        try:
            quota_info = about.get('storageQuota', {})
            if quota_info:
                usage = quota_info.get('usage', 'Unknown')
                limit = quota_info.get('limit', 'Unknown')
                results.append(f"✓ Storage quota: {usage}/{limit} bytes used")
        except:
            results.append("? Could not retrieve quota information")
        
        # Test 7: Check OAuth scopes
        try:
            if hasattr(creds, 'scopes') and creds.scopes:
                scopes_str = ', '.join(str(scope) for scope in creds.scopes)
                results.append(f"✓ OAuth scopes: {scopes_str}")
            else:
                results.append("? OAuth scopes: Unknown or not available")
        except Exception as e:
            results.append(f"? OAuth scopes: Error reading scopes - {str(e)}")
        
        # Test 8: Check if credentials need refresh
        if creds.expired:
            results.append("⚠ Credentials are expired - attempting refresh...")
            try:
                creds.refresh(Request())
                results.append("✓ Credentials refreshed successfully")
                
                # Update session
                session["credentials"] = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes
                }
            except Exception as e:
                results.append(f"✗ Credential refresh failed: {str(e)}")
        else:
            results.append("✓ Credentials are not expired")
            
    except Exception as e:
        results.append(f"✗ Major error in diagnostics: {str(e)}")
        import traceback
        results.append(f"Traceback: {traceback.format_exc()}")
    
    return render_template("diagnostics.html", results=results)


# Add this helper route for the template
@app.route("/diagnostics/template")
def diagnostics_template():
    """Simple template for diagnostics if you don't have one"""
    results = request.args.getlist('results')
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Diagnostics</title>
        <style>
            body { font-family: monospace; margin: 20px; }
            .result { margin: 5px 0; padding: 5px; }
            .success { color: green; }
            .error { color: red; }
            .warning { color: orange; }
        </style>
    </head>
    <body>
        <h1>System Diagnostics</h1>
        <div id="results">
    """
    
    for result in results:
        css_class = "success" if result.startswith("✓") else ("error" if result.startswith("✗") else ("warning" if result.startswith("⚠") else ""))
        html += f'<div class="result {css_class}">{result}</div>'
    
    html += """
        </div>
        <br>
        <a href="/">← Back to Main</a>
        <br><br>
        <form method="POST" action="/refresh/thumbnails">
            <input type="hidden" name="test_mode" value="true">
            <button type="submit">Test Thumbnail Refresh (5 files only)</button>
        </form>
    </body>
    </html>
    """
    
    return html

### - Program Start - ###
if __name__ == "__main__":
    # Initializes the database (creates tables if needed) on startup.
    init_db()

    # Add production configuration
    PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"

    # Update session configuration for production
    app.config['SESSION_COOKIE_SECURE'] = PRODUCTION  # HTTPS only in production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Remove insecure transport for production
    if not PRODUCTION:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    # Update server configuration
    app.run(
        host="0.0.0.0" if PRODUCTION else SERVER_HOST,
        port=SERVER_PORT,
        debug=not PRODUCTION
    )
