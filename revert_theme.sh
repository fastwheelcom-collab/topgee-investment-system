#!/bin/bash

echo "🔄 Reverting to Original Theme..."
echo ""

cd ~/Desktop/TopGee_Investment_System

# Commit the revert
git add templates/dashboard.html
git commit -m "Revert to original dark theme (user preference)"

# Push to GitHub (triggers auto-deploy)
git push origin main

echo ""
echo "✅ Reverted to original theme!"
echo "🌐 Production will update in 2-3 minutes"
echo "🔗 https://topgee-investment-system.onrender.com"
echo ""
