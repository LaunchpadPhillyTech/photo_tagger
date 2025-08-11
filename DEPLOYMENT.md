# DigitalOcean Deployment Checklist for Photo Tagger

## Pre-Deployment Checklist

### 🔧 Local Setup
- [ ] Python 3.11+ installed
- [ ] All dependencies in `requirements.txt`
- [ ] Flask app runs locally without errors
- [ ] SQLite database initializes properly
- [ ] OAuth flow works with localhost URLs

### 📁 Required Files
- [ ] `main.py` (Flask application)
- [ ] `requirements.txt` (Python dependencies)
- [ ] `Procfile` (Process definition)
- [ ] `runtime.txt` (Python version specification)
- [ ] `app.yaml` (DigitalOcean App Platform configuration)
- [ ] `.env` (Environment variables for local)
- [ ] `.env.production` (Template for production environment)

### 🔐 Google OAuth Setup
- [ ] Google Cloud Console project created
- [ ] Google Drive API enabled
- [ ] OAuth 2.0 credentials created (Web application)
- [ ] Local redirect URI added: `http://localhost:3000/callback/oauth2callback`
- [ ] Production redirect URIs ready to add after deployment

### 📊 DigitalOcean Preparation
- [ ] DigitalOcean account created
- [ ] `doctl` CLI installed and configured
- [ ] GitHub repository set up and accessible
- [ ] Domain name ready (optional but recommended)

### 🔑 Environment Variables Ready
- [ ] `GOOGLE_CLIENT_ID` from Google Cloud Console
- [ ] `GOOGLE_CLIENT_SECRET` from Google Cloud Console
- [ ] `GOOGLE_PROJECT_ID` from Google Cloud Console
- [ ] `FLASK_SECRET_KEY` generated (use: `python3 -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `OAUTH_REDIRECT_URI` for production URL

## Deployment Checklist

### 🚀 Pre-Deployment Validation
- [ ] Run `./validate-setup.sh` successfully
- [ ] All Git changes committed and pushed
- [ ] No Python import errors
- [ ] No dependency conflicts

### 📱 DigitalOcean App Platform Deployment
- [ ] Run `./deploy.sh` successfully
- [ ] App builds without errors
- [ ] App starts and becomes ACTIVE
- [ ] Environment variables configured in DO dashboard
- [ ] Volume mount configured for database persistence

### 🔗 Post-Deployment Configuration
- [ ] Get deployed app URL from DigitalOcean
- [ ] Update Google OAuth redirect URIs with production URL
- [ ] Test OAuth authentication flow
- [ ] Verify authorized users can access the application
- [ ] Test photo upload and tagging functionality
- [ ] Test backup and restore functionality

### 🌐 Domain Configuration (Optional)
- [ ] Custom domain configured in DigitalOcean
- [ ] DNS records updated
- [ ] SSL certificate active
- [ ] OAuth redirect URIs updated for custom domain

### 🔍 Monitoring and Validation
- [ ] Application logs show no errors
- [ ] Database operations working
- [ ] Google Drive API calls successful
- [ ] All user flows tested

## Common Issues and Solutions

### OAuth Issues
- **Problem**: `redirect_uri_mismatch`
- **Solution**: Ensure redirect URIs in Google Console exactly match deployed URLs

### Build Failures
- **Problem**: Dependencies not installing
- **Solution**: Check `requirements.txt` and Python version in `runtime.txt`

### Database Issues
- **Problem**: Database not persisting
- **Solution**: Verify volume mount configuration in `app.yaml`

### Environment Variables
- **Problem**: App can't load configuration
- **Solution**: Double-check all environment variables are set in DO dashboard

## Performance Optimization (Post-Deployment)

### Recommended Optimizations
- [ ] Enable application monitoring
- [ ] Set up log aggregation
- [ ] Configure auto-scaling if needed
- [ ] Implement caching for frequently accessed data
- [ ] Monitor database size and performance

### Security Hardening
- [ ] Rotate secrets regularly
- [ ] Monitor access logs
- [ ] Review user permissions
- [ ] Enable security headers
- [ ] Regular dependency updates

## Backup Strategy

### Database Backups
- [ ] Use built-in backup functionality regularly
- [ ] Consider automated backup schedule
- [ ] Test backup restoration process
- [ ] Store critical backups off-platform

### Application Backups
- [ ] Maintain Git repository with all changes
- [ ] Document configuration changes
- [ ] Keep environment variable records secure
- [ ] Maintain deployment runbook

## Support and Troubleshooting

### Useful Commands
```bash
# Check app status
doctl apps list

# View app logs
doctl apps logs <app-id>

# Update app configuration
doctl apps update <app-id> --spec app.yaml

# Get app details
doctl apps get <app-id>
```

### Key URLs
- DigitalOcean Dashboard: https://cloud.digitalocean.com/apps
- Google Cloud Console: https://console.cloud.google.com/
- App Logs: Available in DO dashboard or via CLI
- GitHub Repository: https://github.com/LaunchpadPhillyTech/photo_tagger

### Emergency Contacts
- DigitalOcean Support: Via dashboard ticket system
- Google Cloud Support: Via Google Cloud Console
- Application maintainer: [Your contact information]

---

## Final Deployment Steps Summary

1. **Validate**: `./validate-setup.sh`
2. **Deploy**: `./deploy.sh`
3. **Configure OAuth**: Update redirect URIs in Google Console
4. **Test**: Verify all functionality works
5. **Monitor**: Check logs and performance
6. **Document**: Update this checklist with any issues encountered

**Estimated Deployment Time**: 15-30 minutes
**Estimated Total Setup Time**: 1-2 hours (including OAuth setup)
