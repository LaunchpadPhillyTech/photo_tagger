#!/bin/bash
# Pre-deployment validation script

echo "🔍 Validating Photo Tagger deployment setup..."

# Check required files
echo "📁 Checking required files..."
required_files=("main.py" "requirements.txt" "Procfile" "runtime.txt" "app.yaml" ".env")
missing_files=()

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
        echo "   ❌ Missing: $file"
    else
        echo "   ✅ Found: $file"
    fi
done

if [ ${#missing_files[@]} -gt 0 ]; then
    echo "❌ Missing required files. Please create them before deployment."
    exit 1
fi

# Validate .env file
echo "🔐 Validating environment variables..."
required_vars=("GOOGLE_CLIENT_ID" "GOOGLE_CLIENT_SECRET" "GOOGLE_PROJECT_ID" "FLASK_SECRET_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env; then
        missing_vars+=("$var")
        echo "   ❌ Missing: $var"
    else
        echo "   ✅ Found: $var"
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ Missing required environment variables in .env file."
    echo "💡 Please add the following variables:"
    for var in "${missing_vars[@]}"; do
        echo "   $var=your-value-here"
    done
    exit 1
fi

# Check Git status
echo "📝 Checking Git repository..."
if [ ! -d ".git" ]; then
    echo "❌ Not a Git repository. Please initialize Git and push to GitHub."
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  Uncommitted changes detected:"
    git status --short
    echo "💡 Consider committing these changes before deployment."
else
    echo "✅ Git repository is clean"
fi

# Check if we can reach GitHub
echo "🌐 Checking GitHub connectivity..."
if git ls-remote origin &>/dev/null; then
    echo "✅ GitHub repository is accessible"
else
    echo "❌ Cannot access GitHub repository. Check your remote URL and credentials."
    exit 1
fi

# Validate Python dependencies
echo "🐍 Validating Python dependencies..."
if command -v python3 &> /dev/null; then
    echo "✅ Python3 is installed"
    if pip3 check &>/dev/null; then
        echo "✅ No dependency conflicts detected"
    else
        echo "⚠️  Dependency conflicts detected. Run 'pip3 check' to see details."
    fi
else
    echo "❌ Python3 is not installed"
    exit 1
fi

# Validate Flask app
echo "🌶️  Validating Flask application..."
if python3 -c "import main; print('✅ Flask app imports successfully')" 2>/dev/null; then
    echo "✅ Flask application is valid"
else
    echo "❌ Flask application has import errors"
    python3 -c "import main" 2>&1 | head -5
    exit 1
fi

echo ""
echo "🎉 Validation complete! Your app is ready for deployment."
echo ""
echo "📋 Next steps:"
echo "1. Run './deploy.sh' to deploy to DigitalOcean"
echo "2. Update Google OAuth redirect URIs after deployment"
echo "3. Test the deployed application"
