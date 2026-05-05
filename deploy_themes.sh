#!/bin/bash

echo "🎨 Deploying Theme Updates to Production..."
echo ""

cd ~/Desktop/TopGee_Investment_System

# Add all new files
git add static/css/theme-*.css
git add templates/theme_preview.html
git add app.py
git add templates/dashboard.html

# Commit
git commit -m "Add 3 color theme options (Ocean/Forest/Royal) with mobile optimization"

# Push to GitHub (triggers auto-deploy on Render)
git push origin main

echo ""
echo "✅ Deployment started!"
echo "🌐 Site will update in 2-3 minutes"
echo "🔗 https://topgee-investment-system.onrender.com"
echo ""
echo "After site updates:"
echo "1. Login (admin/admin123)"
echo "2. Click '🎨 Themes' button in navigation"
echo "3. Test all 3 themes on mobile"
echo ""
