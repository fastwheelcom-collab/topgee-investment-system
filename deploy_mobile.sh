#!/bin/bash

echo "📱 Deploying Mobile Optimization..."
echo ""

cd ~/Desktop/TopGee_Investment_System

# Stage changes
git add static/css/style.css

# Commit
git commit -m "Add comprehensive mobile optimization to original dark theme"

# Push to GitHub (auto-deploys to Render)
git push origin main

echo ""
echo "✅ Mobile optimization deployed!"
echo "🌐 Site updates in 2-3 minutes"
echo "🔗 https://topgee-investment-system.onrender.com"
echo ""
echo "Test on your phone - navigation, tables, buttons all mobile-friendly now!"
echo ""
