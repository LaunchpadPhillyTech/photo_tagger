# Photo Tagger

A Flask-based web application for tagging and organizing Google Drive photos with local SQLite storage and backup functionality.

## Features

- **Google Drive Integration**: OAuth2 authentication with read-only access to your Drive files
- **Photo Tagging**: Add, remove, and rename tags for your photos
- **Folder Support**: Process entire Google Drive folders recursively
- **Search Functionality**: Search photos by tags or file IDs
- **Backup System**: Create and restore complete database backups
- **Thumbnail Support**: Automatic thumbnail fetching from Google Drive
- **Responsive UI**: Bootstrap-based interface with pagination

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- Google Cloud Console project with Drive API enabled
- Google OAuth2 credentials

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd photo_tagger
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Google OAuth2 credentials**
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Google Drive API
   - Create OAuth2 credentials (Web application type)
   - Add `http://localhost:3000/callback/oauth2callback` to Authorized redirect URIs

5. **Configure environment variables**
   - Copy `.env.example` to `.env`: `cp .env.example .env`
   - Update the values in `.env` with your Google OAuth credentials
   - Update `ALLOWED_USERS` in `main.py` (lines 33-38) with authorized email addresses

6. **Run the application**
   ```bash
   python main.py
   ```

7. **Access the application**
   - Open your browser and go to `http://localhost:3000`
   - You'll be redirected to Google OAuth for authentication
   - Grant the necessary permissions for Drive access

## Usage

### Adding Photos
- Paste Google Drive file or folder URLs in the upload form
- Add comma-separated tags
- The app will process folders recursively and extract all image files

### Managing Tags
- Click on any tag to remove it from a photo
- Use the "Add Tag" form on each photo to add new tags
- Use the "Rename Tag" section to bulk rename tags across all photos

### Search and Filter
- Use the search bar to find photos by tags or file IDs
- Click on available tags to filter photos
- Combine multiple search terms with commas

### Backup Management
- Create backups with custom names or automatic timestamps
- Load previous backups to restore your data
- Delete old backups to save space

## Development

### Project Structure
```
photo_tagger/
├── main.py              # Main Flask application
├── .env                 # Environment variables (not in git)
├── .env.example         # Environment variables template
├── data/
│   └── data.db         # SQLite database
├── static/
│   └── style.css       # Custom styles
├── templates/
│   └── index.html      # Main template
├── venv/               # Virtual environment (if using pip)
├── requirements.txt    # Python dependencies
└── pyproject.toml      # Poetry configuration
```

### Database Schema
- **images**: Stores file IDs, tags (JSON), and thumbnail URLs
- **backups**: Stores complete database snapshots with timestamps

### Configuration
All configuration constants are defined at the top of `main.py` for easy modification.

## Security Notes

- The application uses read-only Google Drive access
- User access is controlled via email whitelist
- Sessions use secure random keys
- All database operations use parameterized queries

## Troubleshooting

### Common Issues

- **500 Internal Server Error**: Usually caused by OAuth configuration issues
  - Check that your `.env` file exists and contains all required variables
  - Ensure the redirect URI matches exactly in your Google Cloud Console OAuth2 credentials
  - Verify your Google OAuth credentials are correct

- **OAuth errors**: Ensure redirect URI matches exactly in Google Cloud Console
  - Go to Google Cloud Console → APIs & Services → Credentials
  - Edit your OAuth 2.0 Client ID
  - Add `http://localhost:3000/callback/oauth2callback` to Authorized redirect URIs

- **Permission denied (403)**: Check that your email is in the `ALLOWED_USERS` list
  - Edit `main.py` lines 33-38 to include your Google account email

- **Port already in use**: Another process is using port 3000
  ```bash
  # Kill existing processes on port 3000
  lsof -ti:3000 | xargs kill -9
  ```

- **Missing thumbnails**: Some Google Drive files may not have thumbnail support
  - This is normal for certain file types or very large images

- **Database issues**: Delete `data/data.db` to reset (you'll lose all data)
  ```bash
  rm data/data.db
  python main.py  # Will recreate the database
  ```

### Recent Updates

**Configuration Updates:**
- Migrated from `credentials.json` file to environment variable-based OAuth configuration
- Updated default port from 8080 to 3000 to match common development practices
- Enhanced configuration with centralized constants and better error handling

**Environment Setup:**
- Added `.env.example` template file for easy configuration
- Support for both Poetry and pip installation methods
- Improved virtual environment setup instructions for better dependency isolation

**Code Quality:**
- Added Ruff linting and Pyright type checking support
- Enhanced error handling and user feedback
- Improved code organization with clear constant definitions
