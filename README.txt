╔══════════════════════════════════════════════════════════════════╗
║                  SCHOOL MANAGEMENT SYSTEM                       ║
║                      Setup Guide                                ║
╚══════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 WHAT THIS APP DOES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Register pupils with full personal details & profile photo
✅ Record parent/guardian information and emergency contacts
✅ Manage teachers and assign them to classes (Primary 1–6)
✅ Enter results: CA (40 marks) + Exam (60 marks) per subject per term
✅ View results history and overall performance per pupil
✅ Generate printable PDF report cards
✅ Promote pupils to next class at end of academic year
✅ Graduate Primary 6 pupils
✅ Archive and restore pupils
✅ 3-term academic year structure
✅ Separate Admin and Teacher login roles
✅ 11 standard Nigerian primary school subjects pre-loaded
✅ Fee management: set fee structures per class/term, generate bills, record payments
✅ Parent portal: parents log in to view results, fees, download report cards, and acknowledge
✅ School notices: post announcements visible to parents and/or staff
✅ ID card generation and printing for pupils
✅ Daily attendance tracking with absence alerts
✅ WhatsApp/SMS notification hooks for results, fee receipts, absence alerts and broadcasts
✅ Paystack online fee payment initialization and verification flow
✅ Performance analytics dashboard cards for academics and fee collection
✅ Homework, events calendar, timetable, payroll and academic rollover tools
✅ PWA support, dark mode and server-side PDF download endpoints


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Python 3.6 or higher (free download at https://python.org/downloads)
   - On Windows: Check "Add Python to PATH" during installation
   - On Mac: Already installed, or install from python.org
   - No other software needed — everything is included!


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 HOW TO START THE APP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WINDOWS:
  Double-click "start.bat"
  The app will open automatically in your browser.

MAC / LINUX:
  1. Open Terminal
  2. Type: cd [path to this folder]
  3. Type: bash start.sh
  The app will open automatically in your browser.

MANUAL START (any system):
  Open terminal, navigate to this folder, then type:
    python3 server.py     (Mac/Linux)
    python server.py      (Windows)
  Then open your browser and go to: http://localhost:8080


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FIRST ADMIN LOGIN / SECURE BOOTSTRAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For production, set these environment variables before first start:

  INITIAL_ADMIN_NAME
  INITIAL_ADMIN_EMAIL
  INITIAL_ADMIN_PASSWORD

The app now avoids automatically creating an insecure default admin in production.

FOR LOCAL DEVELOPMENT ONLY (optional):
  Set ALLOW_DEFAULT_ADMIN=true if you want the old quick-start admin account.

  Email:    admin@school.com
  Password: admin123

  ⚠️  IMPORTANT: Change this password immediately after first login!
      Go to Settings → Change Admin Password


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 HOW TO USE THE APP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FIRST TIME SETUP (do this in order):

  Step 1 — Settings:
    - Go to Settings → add any additional subjects if needed
    - Confirm the current academic year and term are correct
    - Change the admin password
    - Configure events, homework, timetable, payroll and broadcast tools as needed

  Step 2 — Teachers:
    - Go to Teachers → Add each teacher
    - Give them an email and password (they'll use this to log in)

  Step 3 — Classes:
    - Go to Classes → Assign a teacher to each class (Primary 1–6)

  Step 4 — Pupils:
    - Go to Pupils → Add Pupil
    - Fill in all details including class assignment

  Step 5 — Results:
    - Go to Results
    - Select a Class, Term, and Subject
    - Enter CA scores (max 40) and Exam scores (max 60) for each pupil
    - Click "Save All Results"
    - Use "Publish Results" to notify parents after entry

  Step 6 — Attendance:
    - Go to Attendance
    - Select class and date
    - Mark Present / Late / Absent
    - Save to record attendance and send configured absence alerts

  Step 7 — Report Cards:
    - Go to Pupils → click the eye icon to view a pupil profile
    - Select the term and click "Report Card"
    - The report card will open — click "Print / Save as PDF"
    - In the print dialog, choose "Save as PDF" to get a PDF file

  Step 8 — Parent Portal Additions:
    - Parents can view homework, timetable, notices, fees and report cards
    - Parents can download report/receipt PDFs
    - Parents can use Paystack payment where configured

  Step 9 — Admin Operations Tools:
    - Settings → Calendar & Events
    - Settings → Homework & Assignments
    - Settings → Class Timetable
    - Settings → Broadcast Messages
    - Settings → Payroll
    - Settings → Academic Year Rollover


END OF YEAR — PROMOTION:
    - Go to Classes
    - Click "Promote" on each class
    - Pupils move from Primary 1→2→3→4→5→6
    - Primary 6 pupils are automatically graduated

TEACHER ACCESS:
    - Teachers log in with their email/password
    - They can only see their assigned class
    - They can enter results for their class
    - They can view pupil profiles in their class
    - They can change their own password via Settings

PARENT ACCESS:
    - Go to Settings → Parent Accounts → Add Parent Account
    - Give the parent their email/password
    - Parents log in at the same URL and see a parent-only portal
    - They can view their child's results, fees, report cards, and post acknowledgements


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DATA & BACKUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  All data is stored in the file: school.db
  (created automatically in this folder on first run)

  To BACK UP your data:
    - Simply copy "school.db" to another location (USB drive, Google Drive, etc.)
    - Do this regularly!

  To RESTORE from backup:
    - Stop the server
    - Replace the "school.db" file with your backup copy
    - Start the server again

  NEW:
    - The app can now create timestamped SQLite backups in the backups/ folder
    - Admins can review readiness checks and backups from Settings
    - Health endpoint now reports deployment/readiness summary


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FILE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  school-management/
  ├── server.py          ← The main application (do not delete)
  ├── school.db          ← Your data (back this up regularly!)
  ├── start.bat          ← Windows startup script
  ├── start.sh           ← Mac/Linux startup script
  ├── README.txt         ← This file
  ├── static/
  │   ├── index.html     ← The web interface
  │   ├── css/style.css  ← Styling
  │   └── js/app.js      ← Application logic
  └── uploads/           ← Where profile photos are stored


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FUTURE IMPROVEMENT IDEAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • Attendance register: daily attendance tracking per class
  • Bulk pupil import from Excel/CSV
  • SMS/Email notifications to parents
  • Bulk report card printing for entire class
  • Secondary school expansion (JSS 1–3, SS 1–3)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 INTEGRATIONS / PRODUCTION SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

To enable the new integrations, configure these environment variables:

  Core runtime / security:
    ENVIRONMENT=production
    DATA_DIR=/data
    ALLOWED_ORIGIN=https://your-app.up.railway.app
    INITIAL_ADMIN_NAME
    INITIAL_ADMIN_EMAIL
    INITIAL_ADMIN_PASSWORD
    ALLOW_DEFAULT_ADMIN=false
    ALLOW_DESTRUCTIVE_MIGRATIONS=false
    LOG_LEVEL=INFO

  Paystack:
    PAYSTACK_PUBLIC_KEY
    PAYSTACK_SECRET_KEY
    PAYSTACK_CALLBACK_URL

  Termii WhatsApp / SMS:
    TERMII_API_KEY
    TERMII_SENDER
    TERMII_SMS_ENDPOINT
    TERMII_WHATSAPP_ENDPOINT

  Meta WhatsApp Cloud API (optional alternative):
    META_WHATSAPP_ACCESS_TOKEN
    META_WHATSAPP_PHONE_NUMBER_ID

  General:
    APP_URL

For server-side PDF generation, install WeasyPrint and any OS packages it requires.

Production checklist:
  1. Mount persistent storage and set DATA_DIR
  2. Set ALLOWED_ORIGIN to your real frontend domain
  3. Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD
  4. Configure SMTP if you need email notices
  5. Configure Paystack if you need online payments
  6. Configure Termii or Meta WhatsApp if you need SMS/WhatsApp
  7. Confirm /health returns status=ok after deployment
  8. Create an initial manual backup after first setup


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TESTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run the automated backend checks with:

  python3 -m unittest discover -s tests -v


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SUPPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  If you encounter any issues, common fixes:

  "Address already in use" error:
    → Another server is already running. Close the other terminal window.

  "Python not found" error (Windows):
    → Reinstall Python from python.org and check "Add to PATH"

  App not opening in browser:
    → Manually go to: http://localhost:8080

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
