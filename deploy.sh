#!/bin/bash
# DigitalOcean Deployment Script for Photo Tagger

set -e

echo "🚀 Starting Photo Tagger deployment to DigitalOcean..."

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo "❌ DigitalOcean CLI (doctl) is not installed."
    echo "📥 Install it from: https://docs.digitalocean.com/reference/doctl/how-to/install/"
    exit 1
fi

# Check if user is authenticated
if ! doctl auth list &> /dev/null; then
    echo "❌ You are not authenticated with DigitalOcean."
    echo "🔑 Run: doctl auth init"
    exit 1
fi

# Variables
APP_NAME="photo-tagger"
REPO_URL="https://github.com/LaunchpadPhillyTech/photo_tagger"

echo "� Deployment Configuration:"
echo "   App Name: $APP_NAME"
echo "   Repository: $REPO_URL"

# Validate required files exist
echo "🔍 Checking required files..."
required_files=("app.yaml" "requirements.txt" "Procfile" "runtime.txt" "main.py")

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
    echo "   ✅ $file"
done

# Check for environment variables in .env
echo "🔍 Checking environment configuration..."
if [ ! -f ".env" ]; then
    echo "❌ Missing .env file. Please create it with your configuration."
    exit 1
fi

# Validate Google OAuth configuration
if ! grep -q "GOOGLE_CLIENT_ID=" .env; then
    echo "❌ Missing GOOGLE_CLIENT_ID in .env file"
    exit 1
fi

if ! grep -q "GOOGLE_CLIENT_SECRET=" .env; then
    echo "❌ Missing GOOGLE_CLIENT_SECRET in .env file"
    exit 1
fi

echo "   ✅ Environment configuration looks good"

# Check Git status
echo "🔍 Checking Git status..."

if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  You have uncommitted changes. Commit them first:"
    git status --porcelain
    echo ""
    read -p "Do you want to commit and push changes now? (y/N): " -n 1 -r
    echo
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add .
        read -p "Enter commit message: " commit_message
        git commit -m "$commit_message"
        git push origin main
        echo "✅ Changes committed and pushed"
    else
        echo "❌ Please commit your changes before deploying"
        exit 1
    fi
fi

# Deploy the app
echo "🚀 Deploying to DigitalOcean App Platform..."

# Check if app already exists
if doctl apps list | grep -q "$APP_NAME"; then
    echo "📱 App '$APP_NAME' already exists. Updating..."
    APP_ID=$(doctl apps list --format ID,Name --no-header | grep "$APP_NAME" | awk '{print $1}')
    doctl apps update "$APP_ID" --spec app.yaml
else
    echo "📱 Creating new app '$APP_NAME'..."
    doctl apps create --spec app.yaml
fi

echo "⏳ Waiting for deployment to complete..."
echo "📊 You can monitor the deployment at: https://cloud.digitalocean.com/apps"

# Wait for deployment
APP_ID=$(doctl apps list --format ID,Name --no-header | grep "$APP_NAME" | awk '{print $1}')

while true; do
    STATUS=$(doctl apps get "$APP_ID" --format Phase --no-header)
    
    if [ "$STATUS" = "ACTIVE" ]; then
        echo "✅ Deployment completed successfully!"
        break
    elif [ "$STATUS" = "ERROR" ]; then
        echo "❌ Deployment failed. Check the logs for details."
        doctl apps logs "$APP_ID"
        exit 1
    else
        echo "⏳ Deployment status: $STATUS"
        sleep 30
    fi
done

# Get app URL
APP_URL=$(doctl apps get "$APP_ID" --format LiveURL --no-header)
echo "🌐 Your app is now available at: $APP_URL"

echo ""
echo "📋 Next Steps:"
echo "1. Update your Google OAuth redirect URIs to include: $APP_URL/callback/oauth2callback"
echo "2. Test the OAuth flow by visiting your app"
echo "3. Configure a custom domain if needed"
echo ""
echo "🎉 Deployment complete!"
sudo chown $USER:$USER $APP_DIR

# Clone repository (or copy files)
cd $APP_DIR
git clone $REPO_URL .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn

# Create data directory
mkdir -p data
sudo chown -R www-data:www-data data

# Copy production environment file
cp .env.production .env

# Initialize database
python main.py &
sleep 5
pkill -f main.py

# Set up systemd service
sudo cp photo-tagger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable photo-tagger
sudo systemctl start photo-tagger

# Set up Nginx
sudo cp nginx.conf /etc/nginx/sites-available/photo-tagger
sudo ln -sf /etc/nginx/sites-available/photo-tagger /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Get SSL certificate
sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN

# Start services
sudo systemctl restart nginx
sudo systemctl restart photo-tagger

# Set up firewall
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

echo "✅ Deployment complete!"
echo "🌐 Your app should be available at https://$DOMAIN"
echo "📋 Check status with: sudo systemctl status photo-tagger"