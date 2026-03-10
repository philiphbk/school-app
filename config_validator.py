"""
Configuration Validator for School App
"""

import os
import sys
from pathlib import Path

class ConfigValidator:
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.results = []
        self.errors = []

    def check(self, name, condition, message):
        """Record a check result"""
        status = "✅" if condition else "❌"
        print(f"{status} {name}: {message}")
        self.results.append((name, condition, message))
        if not condition:
            self.errors.append(f"{name}: {message}")

    def validate_all(self):
        """Run all validations"""
        print("\n" + "="*60)
        print("🔍 CONFIGURATION VALIDATION")
        print("="*60 + "\n")

        # Check directories
        print("📁 Checking Directories...")
        for d in ['static', 'static/js', 'static/js/modules', 'static/css', 'templates']:
            path = self.base_path / d
            self.check(f"Dir: {d}", path.exists() and path.is_dir(), f"Path: {path}")

        # Check files
        print("\n📄 Checking Files...")
        files = [
            'static/js/utils.js',
            'static/js/logger.js',
            'static/js/realtime.js',
            'static/js/app-core.js',
            'static/js/app.js',
            'static/js/init.js',
            'static/js/auth.js',
            'static/js/config.js',
            'static/js/modules/dashboard.js',
            'static/js/modules/pupils.js',
            'static/js/modules/teachers.js',
            'static/js/modules/classes.js',
            'static/js/modules/results.js',
            'static/js/modules/fees.js',
            'static/js/modules/payments.js',
            'static/js/modules/archive.js',
            'static/js/modules/settings.js',
            'static/js/modules/parent-portal.js',
            'static/css/style.css',
            'static/css/animations.css',
            'templates/index.html',
        ]

        for f in files:
            path = self.base_path / f
            exists = path.exists() and path.is_file()
            size = f"{path.stat().st_size / 1024:.1f}KB" if exists else "N/A"
            self.check(f"File: {f}", exists, f"Size: {size}")

        # Generate report
        print("\n" + "="*60)
        total = len(self.results)
        passed = sum(1 for _, c, _ in self.results if c)
        failed = total - passed
        pct = (passed / total * 100) if total > 0 else 0

        print(f"✅ PASSED: {passed}/{total}")
        print(f"❌ FAILED: {failed}/{total}")
        print(f"📊 SCORE: {pct:.0f}%\n")

        if failed > 0:
            print("❌ ERRORS:")
            for err in self.errors:
                print(f"   • {err}")

        print("="*60 + "\n")
        return pct >= 90

if __name__ == '__main__':
    validator = ConfigValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)