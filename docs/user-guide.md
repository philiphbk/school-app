# GISL Daycare Nursery & Primary School
## School Management Portal — User Guide

---

> **Three types of users can log in to this portal:**
> - **School Admin** — full access to all modules
> - **Teacher** — access to their own class only
> - **Parent** — access to their child's information only

All users log in at the portal URL using their email address and password.

---

---

# PART 1 — SCHOOL ADMINISTRATOR GUIDE

---

## Logging In

1. Open the portal URL in your browser.
2. Enter your admin email and password.
3. Click **Login**.

If this is your first login and an initial password was set for you, you will be prompted to change it immediately.

---

## Dashboard

The dashboard is the first screen you see after logging in. It shows:

- **Active Pupils** — total number of enrolled pupils
- **Teachers** — total number of active teaching staff
- **Classes** — number of classes in the school
- **Archived** — number of archived (withdrawn) pupils

Below the stat cards is the **Classes Overview** table, listing every class, its assigned teacher, and pupil count.

The **Analytics** panel shows subject averages, fee collection totals, and the top and bottom-performing pupils for the current term.

---

## Pupils

### Viewing and Searching Pupils

Go to **Pupils** from the left navigation. You will see a table of all active pupils. Use the **search bar** to find a pupil by name or admission number. Use the **class filter** dropdown to narrow the list by class.

### Adding a New Pupil

1. Click **Add Pupil**.
2. Fill in the pupil's details:
   - First Name, Last Name, Other Name
   - Date of Birth, Gender
   - Class (select from dropdown)
   - Blood Group, Religion
   - Photo (optional, max 2 MB)
3. Fill in parent/guardian details:
   - Parent Name, Phone, Email, Address, Relationship
   - Emergency Contact Name and Phone
4. Fill in medical details if applicable:
   - Allergies, Medical Conditions, Doctor Name, Doctor Phone
5. Click **Save**.

> The system will auto-generate an admission number (format: `SCH/YEAR/NUMBER`) if you leave that field blank.

### Editing a Pupil

Click the **Edit** icon on any pupil row to open the edit form. Update the required fields and click **Save**.

### Archiving a Pupil (Withdrawal)

Click **Archive** on the pupil row. The pupil will be moved to the **Archive** section and removed from the active list. This does not delete their records.

### Restoring an Archived Pupil

Go to **Archive**, find the pupil, and click **Restore**. They will return to the active pupils list.

### Promoting Pupils to the Next Class

1. Click **Promote** on any class or use the promotion button in the pupils list.
2. Select which pupils to promote (tick checkboxes).
3. Confirm the target class.
4. Click **Promote Selected**.

Each selected pupil is moved to the next class. Pupils you do not select remain in their current class.

### Exporting Pupils

- **Export All Pupils** — downloads a CSV file of all pupil records.
- **Export Parent Contacts** — downloads a CSV of parent names, phones, and emails.

### Printing ID Cards

Select one or more pupils and click **Print ID Cards**. A print-ready page will open showing each pupil's photo, name, and admission number.

---

## Teachers

### Viewing Teachers

Go to **Teachers** from the navigation. You will see a list of all active staff with their names, emails, phone numbers, and assigned class.

### Adding a Teacher

1. Click **Add Teacher**.
2. Enter the teacher's name, email, phone, and a temporary password.
3. Optionally assign them to a class immediately.
4. Click **Save**.

The teacher can log in straight away using the email and password you set. They should change their password on first login.

### Editing a Teacher

Click **Edit** on the teacher row to update their name, phone number, or class assignment.

### Deleting a Teacher

Click **Delete** to deactivate the teacher. They will no longer be able to log in. Their history (results entered, attendance marked) is preserved.

---

## Classes

Go to **Classes** to see all classes in the school. Each card shows the class name, level, assigned teacher, and current pupil count.

### Assigning a Teacher to a Class

1. Click **Assign Teacher** on the class card.
2. Select a teacher from the dropdown.
3. Click **Save**.

A teacher can only be assigned to one class at a time. Assigning them to a new class automatically unassigns them from their previous one.

---

## Results

### Entering Results

1. Go to **Results** from the navigation.
2. Select a **Class** and a **Term**.
3. Click **Load Marksheet**.
4. The marksheet shows one row per pupil and one column pair (CA + Exam) per subject.
5. Type in each pupil's scores.
6. Click **Save Results**.

> CA (Continuous Assessment) and Exam scores are entered separately. The system calculates totals automatically.

### Publishing Results to Parents

Once results are entered and ready:

1. Still on the Results page, click **Publish Results**.
2. Choose whether to publish for the whole class or a specific pupil.
3. Confirm.

Parents will receive a notification (WhatsApp/SMS) and can then view their child's results in the parent portal.

---

## Daily Attendance

### Marking Attendance

1. Go to **Attendance** from the navigation.
2. Select a **Class** and a **Date** (defaults to today).
3. Click **Load Register**.
4. For each pupil, select: **Present**, **Late**, or **Absent**.
5. Add an optional note if needed.
6. Click **Save Attendance**.

Parents are automatically notified when their child is marked **Absent**.

---

## Fee Management

### Setting Up Fee Structures

1. Go to **Fees** → **Fee Structure** tab.
2. Click **Add Fee Item**.
3. Fill in:
   - Fee Name (e.g., "School Fees", "Development Levy")
   - Academic Year and Term Number
   - New Pupil Amount and Returning Pupil Amount
   - Class (leave blank to apply to all classes)
4. Click **Save**.

Repeat this for every fee component per term.

### Generating Bills and Recording Payments

1. Go to **Fees** → **Bill** tab.
2. Select a **Class** and **Term**.
3. The bill table shows every pupil with their expected fees, amount paid, and outstanding balance.
4. To record a payment, click **Record Payment** next to a pupil.
5. Enter: amount paid, payment date, payment reference, and any notes.
6. Click **Save**.

### Exporting the Fee Bill

Click **Export CSV** on the Bill tab to download the full fee report for the selected class and term.

---

## Archive

The Archive section has two tabs:

- **Archived Pupils** — pupils who have been withdrawn. You can restore them from here.
- **Graduated Pupils** — pupils who completed the school programme.

---

## Settings

### Academic Terms

1. Go to **Settings** → **Academic Terms**.
2. Click **Add Term**.
3. Enter the academic year (e.g., `2025/2026`), term number (1, 2, or 3), start date, and end date.
4. Click **Save**.

To make a term the current term, click **Set as Current** next to it. Only one term can be current at a time.

### Subjects

1. Go to **Settings** → **Subjects**.
2. Click **Add Subject** and enter the subject name.
3. To hide a subject from the marksheet without deleting it, toggle it **Inactive**.

### Parent Accounts

Parent accounts give parents access to the portal.

1. Go to **Settings** → **Parent Accounts**.
2. Click **Add Parent Account**.
3. Enter the parent's name, email, phone, and a temporary password.
4. Click **Save**.

> The parent's email must match the email recorded on their child's pupil profile. This is how the system links a parent to their child.

### School Notices

1. Go to **Settings** → **Notices**.
2. Click **Post Notice**.
3. Enter a title and body text.
4. Set the audience: **All**, **Parents Only**, or **Staff Only**.
5. Click **Post**.

To remove a notice, click **Delete**. To hide it temporarily, toggle it inactive.

### Calendar & Events

1. Go to **Settings** → **Events**.
2. Click **Add Event**.
3. Enter the event title, date, description, type (holiday, exam, activity, etc.), and audience.
4. Click **Save**.

### Homework & Assignments

1. Go to **Settings** → **Homework**.
2. Click **Add Homework**.
3. Select the class, subject, term, and enter the title, description, and due date.
4. Click **Save**.

Parents and teachers can see homework from the portal. Parents can mark their child's homework as done.

### Class Timetable

1. Go to **Settings** → **Timetable**.
2. Select a class.
3. Click **Add Entry** to add a period: day, start time, end time, subject/period name, and teacher.
4. Click **Save**.

Parents and teachers can view the timetable in the portal.

### Broadcast Messages

Use Broadcast to send a message to all parents or a group at once.

1. Go to **Settings** → **Broadcast**.
2. Choose the target:
   - **All Parents**
   - **Debtors Only** (parents with outstanding fees)
   - **Specific Class**
3. Choose the channel: SMS + WhatsApp, WhatsApp Only, SMS Only, or Email Only.
4. Type your message.
5. Click **Send**.

> Broadcast requires the messaging provider (Termii/WhatsApp) to be configured in environment settings.

### Payroll

1. Go to **Settings** → **Payroll**.
2. Click **Add Entry**.
3. Select the staff member, enter the amount, pay period, payment date, and any notes.
4. Click **Save**.

### Academic Year Rollover

Run the rollover at the end of each academic year to prepare the system for the new year.

1. Go to **Settings** → **Rollover**.
2. Enter the new academic year (e.g., `2026/2027`).
3. Click **Run Rollover**.

The rollover promotes all active pupils to their next class, resets results, and clears attendance records. Pupil profiles and fee history are preserved.

> **This action cannot be undone. Create a backup first.**

### Backups

1. Go to **Settings** → **Backups**.
2. Click **Create Backup** and enter an optional label (e.g., `pre-rollover`).
3. Click **Save**.
4. Download the backup file from the list below.

It is good practice to create a backup before any major operation (rollover, bulk delete, etc.).

### Audit Log

Go to **Settings** → **Audit Log** to see a timestamped record of every action performed in the system — logins, edits, deletions, broadcasts — including which user performed the action and from which IP address.

### Change Password

Go to **Settings** → **Change Password**, enter your new password twice, and click **Save**.

---

---

# PART 2 — TEACHER GUIDE

---

## Logging In

1. Open the portal URL in your browser.
2. Enter your teacher email and password (provided by the admin).
3. Click **Login**.

If prompted to change your password, create a new one before continuing.

---

## Dashboard

The teacher dashboard shows stats and analytics for your assigned class only. You will see:

- Pupil count for your class
- Subject averages for your class
- Top and bottom performers in your class this term

---

## Pupils (Your Class Only)

Go to **Pupils** to see the list of pupils in your assigned class. You can search by name.

You can view and edit a pupil's contact details and medical information. You cannot change a pupil's class, create new pupils, or archive pupils — those are admin functions.

---

## Results

### Entering Results for Your Class

1. Go to **Results**.
2. Your class is pre-selected. Select the **Term**.
3. Click **Load Marksheet**.
4. Enter each pupil's **CA score** and **Exam score** for each subject.
5. Click **Save Results**.

Totals are calculated automatically. You can save multiple times — each save updates the scores.

### Publishing Results

Once you are satisfied with the results:

1. Click **Publish Results**.
2. Confirm the action.

Parents will be notified and can then view their child's results in the parent portal. You can only publish results for your own class.

---

## Daily Attendance

### Marking Your Class Register

1. Go to **Attendance**.
2. Your class is pre-selected. Select the date (defaults to today).
3. Click **Load Register**.
4. Mark each pupil as **Present**, **Late**, or **Absent**.
5. Add an optional note per pupil if needed.
6. Click **Save Attendance**.

Parents receive an automatic notification when their child is marked absent.

---

## Homework

### Setting Homework

1. Go to **Homework** (under Settings or from the navigation).
2. Click **Add Homework**.
3. Your class is pre-filled. Select the subject, term, and enter the title, description, and due date.
4. Click **Save**.

### Managing Homework

You can edit or archive (remove) any homework you have created. You can also see which pupils have had their homework marked as done by their parents.

---

## Conduct Ratings

At the end of each term, rate each pupil's conduct:

1. Select your class and the term.
2. For each pupil, assign grades for:
   - **Conduct** (overall behaviour)
   - **Effort**
   - **Punctuality**
3. Add a **Teacher's Comment**.
4. Click **Save**.

These ratings appear on the pupil's report card.

---

## Skill Assessments (Lower School)

For nursery and primary classes, rate each pupil's developmental skills each term:

1. Select your class and term.
2. For each pupil, assign a grade (A–F) for:
   - Fine Motor, Gross Motor, Social, Cognitive, Language, Emotional
3. Add a comment.
4. Click **Save**.

---

## Notices

You can read all school notices. You can also post new notices:

1. Go to **Notices** in Settings.
2. Click **Post Notice**.
3. Enter a title, body, and audience (All, Parents Only, or Staff Only).
4. Click **Post**.

You can edit or delete notices you have posted.

---

## Calendar & Events

You can view all school events. You can also create events:

1. Go to **Events** in Settings.
2. Click **Add Event**.
3. Fill in the title, date, type, and audience.
4. Click **Save**.

---

## Timetable

Go to **Timetable** to view your class schedule. Contact the admin if changes need to be made.

---

## Parent Acknowledgments

Go to **Acknowledgments** to see which parents have reviewed and acknowledged their child's results for the current term. This helps you follow up with parents who have not yet responded.

---

## Change Password

Go to **Settings** → **Change Password**, enter your new password twice, and click **Save**.

---

---

# PART 3 — PARENT GUIDE

---

## Logging In

1. Open the portal URL in your browser.
2. Enter your email address and password (provided by the school admin).
3. Click **Login**.

If it is your first time logging in or you were told to change your password, you will be asked to create a new one before continuing.

> Your email address must match the one the school has on file for your child. If you cannot log in, contact the school office.

---

## My Children

After logging in, you will see the **My Children** screen with a card for each of your children enrolled at the school. Click on a child's card to view their details.

If you have more than one child at the school and their profiles are all linked to your email, you will see all of them here.

---

## Child Detail — Tabs

Each child's page has several tabs.

---

### Results Tab

1. Select the **Term** from the dropdown.
2. View your child's results:
   - Each subject showing CA (Continuous Assessment) and Exam scores
   - The total for each subject
   - The grand total across all subjects
3. After reviewing, you can **acknowledge** the results:
   - Tick the acknowledgment checkbox
   - Add an optional comment for the teacher
   - Click **Save Acknowledgment**

> Results only appear after the teacher has published them for the term.

---

### Fees Tab

1. Select the **Term** from the dropdown.
2. View the fee bill for your child:
   - Each fee item (e.g., School Fees, Development Levy)
   - Amount expected
   - Amount paid to date
   - Outstanding balance
   - Payment status (Paid in Full or Outstanding)
3. Scroll down to see the full **payment history** with dates and references.

#### Paying Fees Online

If online payment is enabled:

1. Click **Make Payment**.
2. You will be redirected to the payment gateway (Paystack).
3. Complete the payment using your card or bank transfer.
4. You will be returned to the portal and the payment will be recorded automatically.

#### Downloading a Receipt

Click **Download Receipt** to save or print a PDF fee receipt for the selected term.

---

### Report Card Tab

1. Select the **Term** from the dropdown.
2. View your child's full report card, including:
   - All subject scores (CA, Exam, Total)
   - Attendance summary (Present, Late, Absent, Total Days)
   - Performance trend (comparison with previous terms)
3. Click **Print / Save PDF** to download a copy.

---

### Homework Tab

1. Select the **Term** from the dropdown.
2. View all homework assignments set for your child's class:
   - Subject, title, description, and due date
3. To mark an assignment as done:
   - Tick the **Completed** checkbox next to the assignment
   - Add an optional note to the teacher
   - The status is saved automatically

---

### Timetable Tab

View your child's class timetable. The timetable shows each day of the week with the periods, subjects, and teachers.

---

## School Notices

Go to **Notices** from the navigation to read the latest announcements from the school. Notices are displayed in order from newest to oldest.

---

## School Events / Calendar

Some portals show upcoming school events (term dates, holidays, exam schedules, activities). Check the calendar or events section for this information.

---

## Change Password

1. Click your name or **Settings** at the bottom of the navigation.
2. Select **Change Password**.
3. Enter your new password twice.
4. Click **Save**.

---

## Installing the Portal on Your Phone

The portal can be installed as an app on your phone without going through an app store:

**On Android (Chrome):**
1. Open the portal in Chrome.
2. Tap the three-dot menu.
3. Tap **Add to Home Screen**.

**On iPhone (Safari):**
1. Open the portal in Safari.
2. Tap the Share button.
3. Tap **Add to Home Screen**.

The portal will appear as an icon on your home screen and open like a regular app.

---

## Getting Help

If you have trouble logging in or cannot find information about your child, contact the school office directly. Provide your registered email address when you call or visit.

---

---

*GISL Daycare Nursery & Primary School — School Management Portal*
