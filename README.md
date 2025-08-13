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

## 🚀 DigitalOcean Deployment Guide

### Prerequisites for Deployment

- DigitalOcean account
- Domain name (optional but recommended)
- Google Cloud Console project with Drive API enabled
- Git repository (GitHub/GitLab)

### Step 1: Prepare Your Application for Production

1. **Update OAuth Redirect URIs in Google Cloud Console**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to APIs & Services → Credentials
   - Edit your OAuth 2.0 Client ID
   - Add your production URLs to "Authorized redirect URIs":
     ```
     https://yourdomain.com/callback/oauth2callback
     https://your-app-name.ondigitalocean.app/callback/oauth2callback
     ```

2. **Generate a secure Flask secret key**
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

### Step 2: Create DigitalOcean App Platform Application

1. **Log into DigitalOcean and create a new App**
   - Go to [DigitalOcean Dashboard](https://cloud.digitalocean.com/)
   - Click "Create" → "Apps"

2. **Connect your repository**
   - Choose GitHub or GitLab
   - Select your photo_tagger repository
   - Choose the `main` branch

3. **Configure the App**
   - **Name**: `photo-tagger` (or your preferred name)
   - **Region**: Choose closest to your users
   - **Plan**: Basic ($5/month minimum for persistent storage)

### Step 3: Configure Environment Variables

In the DigitalOcean App Platform settings, add these environment variables:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_PROJECT_ID=your-google-project-id

# OAuth URLs (replace yourdomain.com with your actual domain)
OAUTH_REDIRECT_URI=https://yourdomain.com/callback/oauth2callback

# Flask Configuration
FLASK_SECRET_KEY=your-generated-secret-key-from-step-1
PRODUCTION=true

# Application Configuration
PORT=8080
```

### Step 4: Configure App Spec

Create or update your `app.yaml` file:

```yaml
name: photo-tagger
services:
- name: web
  source_dir: /
  github:
    repo: your-username/photo_tagger
    branch: main
  run_command: gunicorn --bind 0.0.0.0:$PORT main:app
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: GOOGLE_CLIENT_ID
    scope: RUN_TIME
    type: SECRET
  - key: GOOGLE_CLIENT_SECRET
    scope: RUN_TIME
    type: SECRET
  - key: GOOGLE_PROJECT_ID
    scope: RUN_TIME
    type: SECRET
  - key: OAUTH_REDIRECT_URI
    scope: RUN_TIME
    type: SECRET
  - key: FLASK_SECRET_KEY
    scope: RUN_TIME
    type: SECRET
  - key: PRODUCTION
    scope: RUN_TIME
    value: "true"
  - key: PORT
    scope: RUN_TIME
    value: "8080"
  http_port: 8080
  routes:
  - path: /
```

### Step 5: Add Required Deployment Files

1. **Create `runtime.txt`** (specify Python version):
   ```
   python-3.11.9
   ```

2. **Update `requirements.txt`** to ensure all dependencies are listed:
   ```
   Flask==2.3.3
   google-auth==2.23.4
   google-auth-oauthlib==1.1.0
   google-auth-httplib2==0.1.1
   google-api-python-client==2.108.0
   python-dotenv==1.0.0
   gunicorn==21.2.0
   pysqlite3-binary==0.5.2
   ```

3. **Create `Procfile`** for process definition:
   ```
   web: gunicorn --bind 0.0.0.0:$PORT main:app
   ```

### Step 6: Database Persistence Setup

DigitalOcean App Platform has ephemeral storage by default. For persistent SQLite database:

1. **Option A: Use DigitalOcean Managed Database (Recommended)**
   - Create a PostgreSQL database in DigitalOcean
   - Modify your app to use PostgreSQL instead of SQLite
   - This requires code changes but provides better scalability

2. **Option B: Use Volume Mount (Current SQLite approach)**
   - Add a volume mount to your app.yaml:
   ```yaml
   - name: data-volume
     type: VOLUME
     size: 1GB
     mount_path: /app/data
   ```

### Step 7: Deploy the Application

1. **Push your changes to Git**:
   ```bash
   git add .
   git commit -m "Configure for DigitalOcean deployment"
   git push origin main
   ```

2. **Deploy via DigitalOcean Dashboard**:
   - Your app will automatically deploy when you push to the main branch
   - Monitor the build logs in the DigitalOcean dashboard

3. **Wait for deployment** (usually 5-10 minutes)

### Step 8: Post-Deployment Configuration

1. **Test OAuth Flow**:
   - Visit your deployed app URL
   - Try logging in with Google OAuth
   - Verify that authorized users can access the application

2. **Initialize Database**:
   - The database will be automatically initialized on first run
   - Test by adding a photo and some tags

3. **Set up Custom Domain** (Optional):
   - In DigitalOcean dashboard, go to Settings → Domains
   - Add your custom domain
   - Update DNS records as instructed
   - Update OAuth redirect URIs in Google Console

### Step 9: Monitoring and Maintenance

1. **Monitor Application Logs**:
   ```bash
   # View logs in DigitalOcean dashboard or via CLI
   doctl apps logs your-app-id
   ```

2. **Set up Alerts**:
   - Configure uptime monitoring
   - Set up error rate alerts

3. **Regular Backups**:
   - Use the built-in backup functionality
   - Consider automated database backups

### 📋 Deployment Checklist

- [ ] Google OAuth credentials configured with production URLs
- [ ] Environment variables set in DigitalOcean
- [ ] `requirements.txt` updated with all dependencies
- [ ] `Procfile` created for gunicorn
- [ ] `runtime.txt` specifies Python version
- [ ] Database persistence configured
- [ ] Code pushed to Git repository
- [ ] App deployed and accessible
- [ ] OAuth flow tested and working
- [ ] Authorized users can access the application
- [ ] Custom domain configured (if applicable)

### 🔧 Troubleshooting

**Common Issues and Solutions:**

1. **OAuth Redirect URI Mismatch**:
   - Verify redirect URIs in Google Cloud Console match your deployed URLs exactly
   - Check both HTTP and HTTPS variants if needed

2. **Environment Variables Not Loading**:
   - Verify all environment variables are set in DigitalOcean dashboard
   - Check for typos in variable names

3. **Database Not Persisting**:
   - Ensure volume mount is configured correctly
   - Consider migrating to managed PostgreSQL for production

4. **Build Failures**:
   - Check that all dependencies are in `requirements.txt`
   - Verify Python version in `runtime.txt` is supported

5. **Application Won't Start**:
   - Check application logs in DigitalOcean dashboard
   - Verify `Procfile` command is correct

### 💡 Production Optimization Tips

1. **Use a CDN** for static files
2. **Enable GZIP compression** in your Flask app
3. **Set up database connection pooling**
4. **Implement caching** for frequently accessed data
5. **Monitor performance** with DigitalOcean monitoring tools

### 🔐 Security Considerations

1. **Always use HTTPS** in production
2. **Rotate secrets** regularly
3. **Review user access** permissions
4. **Monitor access logs** for suspicious activity
5. **Keep dependencies updated**

---

## Local Development Setup

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

### Debug Tools (very bottom)
- Refresh thumbnails that are potentially broken
- Clear all thumbnails to test auto refresh functionality
- Diagnose issues when editing the program locally

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

**Thumbnail System Overhaul:**
- Fixed thumbnail validation to accept current Google Drive URL formats
- Added comprehensive debugging and diagnostic tools
- Implemented batch thumbnail refresh with error recovery
- Enhanced thumbnail URL validation logic for better reliability

**Debug and Diagnostics:**
- Added /diagnostics route for system health checks
- Implemented detailed error logging and reporting
- Added test modes for safe troubleshooting
- Enhanced batch processing with progress monitoring
