#!/bin/bash

echo "=========================================="
echo "Git Cleanup Script"
echo "=========================================="
echo ""
echo "This script will:"
echo "  1. Remove __pycache__ folders from Git"
echo "  2. Remove supabase folder from Git"
echo "  3. Commit the changes"
echo "  4. Push to GitHub"
echo ""
echo "Files will remain on your local system."
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Removing files from Git tracking..."

# Remove __pycache__ directories
git rm -r --cached app/__pycache__ 2>/dev/null && echo "✓ Removed app/__pycache__" || echo "⊘ app/__pycache__ not tracked"
git rm -r --cached app/api/__pycache__ 2>/dev/null && echo "✓ Removed app/api/__pycache__" || echo "⊘ app/api/__pycache__ not tracked"
git rm -r --cached app/routers/__pycache__ 2>/dev/null && echo "✓ Removed app/routers/__pycache__" || echo "⊘ app/routers/__pycache__ not tracked"
git rm -r --cached app/utils/__pycache__ 2>/dev/null && echo "✓ Removed app/utils/__pycache__" || echo "⊘ app/utils/__pycache__ not tracked"
git rm -r --cached migrations/__pycache__ 2>/dev/null && echo "✓ Removed migrations/__pycache__" || echo "⊘ migrations/__pycache__ not tracked"

# Remove supabase folder
git rm -r --cached supabase/ 2>/dev/null && echo "✓ Removed supabase/" || echo "⊘ supabase/ not tracked"

echo ""
echo "Committing changes..."
git commit -m "chore: Remove __pycache__ and supabase folders from version control

- Added comprehensive .gitignore rules
- Removed Python cache files from tracking
- Removed supabase configuration folder from tracking
- Files remain in local development environment"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Changes committed successfully!"
    echo ""
    echo "Pushing to GitHub..."
    git push

    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✓ SUCCESS!"
        echo "=========================================="
        echo ""
        echo "The __pycache__ and supabase folders have been"
        echo "removed from your GitHub repository."
        echo ""
        echo "They still exist locally and will be ignored"
        echo "in future commits thanks to .gitignore"
    else
        echo ""
        echo "❌ Push failed. Please check your connection and try:"
        echo "   git push"
    fi
else
    echo ""
    echo "No changes to commit (files may not be tracked)"
fi
