# TopGee It - Theme Preview Server
# Quick start script for testing color schemes

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "🎨 TOPGEE IT - THEME PREVIEW" -ForegroundColor Yellow
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "Starting local server..." -ForegroundColor Green
Write-Host "`n📱 Open this link on your phone/computer:" -ForegroundColor Yellow
Write-Host "   http://localhost:5001`n" -ForegroundColor White

Write-Host "🎨 Theme Options:" -ForegroundColor Cyan
Write-Host "   1. Ocean Blue - Professional & Trustworthy" -ForegroundColor Blue
Write-Host "   2. Forest Green - Wealth & Growth" -ForegroundColor Green
Write-Host "   3. Royal Purple - Premium & Luxury" -ForegroundColor Magenta

Write-Host "`n💡 Instructions:" -ForegroundColor Yellow
Write-Host "   1. Login (admin/admin123)"
Write-Host "   2. Click '🎨 Themes' in navigation"
Write-Host "   3. Test all 3 options on mobile & desktop"
Write-Host "   4. Tell me which one you like!"
Write-Host "`n⏹️  Press Ctrl+C to stop server`n" -ForegroundColor Red

Write-Host "============================================`n" -ForegroundColor Cyan

# Start Flask app
python app.py
