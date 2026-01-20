from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import os
import secrets
from utils import (load_users, save_user, authenticate_user, load_jobs, save_job, 
                   class_based_compatibility, save_resume, get_user_resume, get_user_resumes,
                   basic_resume_analysis, get_job_by_id, save_application, get_user_applications,
                   get_hr_jobs_with_applications, update_application_status, get_system_stats,
                   initialize_admin, get_resume_by_id, deep_resume_analysis, check_job_satisfaction, 
                   bulk_update_applications, delete_user, delete_job, update_job_status, get_all_jobs,
                   extract_and_parse_resumes, screen_candidates, save_candidate_to_pool, get_candidate_pool,
                   update_candidate_decision, get_recent_activity, get_system_metrics)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

DEFAULT_JOB_ROLES = [
    "Software Engineer", "Frontend Developer", "Backend Developer", "Full Stack Developer",
    "Data Scientist", "Data Analyst", "Machine Learning Engineer", "DevOps Engineer",
    "System Administrator", "Network Engineer", "Cybersecurity Analyst", "Product Manager",
    "UX/UI Designer", "QA Engineer", "Cloud Architect", "Database Administrator"
]

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

# Initialize CSVs if not exist
import os
if not os.path.exists('data/users.csv'):
    with open('data/users.csv', 'w') as f:
        f.write('id,username,password,role,email\n')
    initialize_admin() # Initialize admin if creating fresh
else:
    # Attempt to init admin even if file exists (e.g. if it was manually deleted from csv)
    initialize_admin()

if not os.path.exists('data/jobs.csv'):
    with open('data/jobs.csv', 'w') as f:
        f.write('id,hr_id,title,description,skills_required,vacancies,status\n')
if not os.path.exists('data/resumes.csv'):
    with open('data/resumes.csv', 'w') as f:
        f.write('id,user_id,filename,content_text,upload_date,file_path\n')
if not os.path.exists('data/candidate_pool.csv'):
    with open('data/candidate_pool.csv', 'w') as f:
        f.write('id,job_id,filename,content_text,score,recommendation,justification,hr_decision,upload_date,file_path\n')
if not os.path.exists('data/applications.csv'):
    with open('data/applications.csv', 'w') as f:
        f.write('id,job_id,user_id,resume_id,status,hr_notes,score,eligibility\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET'])
def register_selection():
    return render_template('register_selection.html')

@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if role not in ['user', 'hr']:
        return redirect(url_for('register_selection'))
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Role is determined by the route
        target_role = role
            
        if save_user(username, password, target_role, email):
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email already registered!', 'error')
            return redirect(url_for('register', role=role))
            
    return render_template('register.html', role=role)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = authenticate_user(email, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            if user['role'] == 'user':
                return redirect(url_for('user_dashboard'))
            elif user['role'] == 'hr':
                return redirect(url_for('hr_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    resumes = get_user_resumes(user_id)
    # Default to the most recent resume for analysis display if available
    resume = resumes[-1] if resumes else None
    
    jobs = load_jobs()
    applications = get_user_applications(user_id)
    
    analysis = None
    if resume:
        # Re-run basic analysis for display
        score, suggestions = basic_resume_analysis(resume['content_text'])
        analysis = {
            'filename': resume['filename'],
            'upload_date': resume['upload_date'],
            'ats_score': score,
            'suggestions': suggestions,
            'id': resume['id']
        }
        
    return render_template('user_dashboard.html', analysis=analysis, jobs=jobs, applications=applications, resumes=resumes, default_roles=DEFAULT_JOB_ROLES)

@app.route('/user/upload_resume', methods=['POST'])
def upload_resume():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if 'resume' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('user_dashboard'))
        
    file = request.files['resume']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('user_dashboard'))
        
    if file:
        filename = secure_filename(file.filename)
        save_resume(session['user_id'], filename, file)
        flash('Resume uploaded successfully with deep analysis!', 'success')
        return redirect(url_for('user_dashboard'))

@app.route('/user/check_satisfaction', methods=['GET', 'POST'])
def check_satisfaction():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))

    result = None
    resumes = get_user_resumes(session['user_id'])
    
    if request.method == 'POST':
        job_description = request.form['job_description']
        resume_id = request.form.get('resume_id')
        
        resume = None
        if resume_id:
            resume = get_resume_by_id(resume_id)
        elif resumes:
            resume = resumes[-1] # Default to latest
            
        if not resume:
            flash('Please upload a resume first!', 'error')
            return redirect(url_for('user_dashboard'))
            
        score, missing = check_job_satisfaction(resume['content_text'], job_description)
        result = {
            'score': score,
            'missing_keywords': missing,
            'analyzed_resume': resume['filename']
        }
        
    return render_template('check_satisfaction.html', result=result, resumes=resumes)

@app.route('/user/check_eligibility/<job_id>', methods=['POST'])
def check_eligibility(job_id):
    """Check eligibility for a specific job with detailed analysis."""
    if 'user_id' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    resume_id = request.form.get('resume_id')
    if not resume_id:
        flash('Please select a resume.', 'error')
        return redirect(url_for('user_dashboard'))
    
    resume = get_resume_by_id(resume_id)
    job = get_job_by_id(job_id)
    
    if not resume or not job:
        flash('Invalid resume or job.', 'error')
        return redirect(url_for('user_dashboard'))
    
    job_description = f"{job['title']} {job['description']} {job['skills_required']}"
    score, details = check_job_satisfaction(resume['content_text'], job_description, detailed=True)
    
    result = {
        'job_title': job['title'],
        'score': score,
        'eligibility_level': details['eligibility_level'],
        'recommendation': details['recommendation'],
        'missing_technical': details.get('missing_technical', []),
        'missing_general': details.get('missing_general', []),
        'matched_count': details['matched_count'],
        'total_keywords': details['total_keywords']
    }
    
    # Return JSON for AJAX request or redirect
    from flask import jsonify
    return jsonify(result)

@app.route('/user/apply/<job_id>', methods=['POST'])
def apply_job(job_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    resume_id = request.form.get('resume_id')
    if not resume_id:
        flash('Please select a resume to apply.', 'error')
        return redirect(url_for('user_dashboard'))

    resume = get_resume_by_id(resume_id)
    if not resume or str(resume['user_id']) != str(session['user_id']):
        flash('Invalid resume selected.', 'error')
        return redirect(url_for('user_dashboard'))
        
    job = get_job_by_id(job_id)
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('user_dashboard'))
        
    # Check compatibility with detailed analysis
    job_description = f"{job['title']} {job['description']} {job['skills_required']}"
    score, details = check_job_satisfaction(resume['content_text'], job_description, detailed=True)
    eligibility = details.get('eligibility_level', 'Medium')
    
    if save_application(job_id, session['user_id'], resume['id'], score, eligibility):
        flash(f'Applied successfully with {resume["filename"]}! Compatibility: {score}% ({eligibility} match)', 'success')
    else:
        flash('You have already applied to this job.', 'warning')
        
    return redirect(url_for('user_dashboard'))

@app.route('/hr/dashboard')
def hr_dashboard():
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
        
    job_applications = get_hr_jobs_with_applications(session['user_id'])
    return render_template('hr_dashboard.html', job_applications=job_applications, default_roles=DEFAULT_JOB_ROLES)

@app.route('/hr/post_job', methods=['POST'])
def post_job():
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
        
    title = request.form['title']
    description = request.form['description']
    skills = request.form['skills']
    vacancies = request.form['vacancies']
    
    save_job(session['user_id'], title, description, skills, vacancies)
    flash('Job posted successfully!', 'success')
    return redirect(url_for('hr_dashboard'))

@app.route('/hr/update_app', methods=['POST'])
def update_application():
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
        
    app_id = request.form['app_id']
    notes = request.form['notes']
    action = request.form['action']
    
    status = 'Selected' if action == 'select' else 'Rejected'
    
    update_application_status(app_id, status, notes)
    flash(f'Candidate {status}!', 'success')
    return redirect(url_for('hr_dashboard'))

    update_application_status(app_id, status, notes)
    flash(f'Candidate {status}!', 'success')
    update_application_status(app_id, status, notes)
    flash(f'Candidate {status}!', 'success')
    return redirect(url_for('hr_dashboard'))

@app.route('/hr/bulk_update_apps', methods=['POST'])
def bulk_update_apps():
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
        
    # Get list of selected app IDs
    app_ids = request.form.getlist('app_ids')
    action = request.form['action']
    justification = request.form['justification']
    
    if not app_ids:
        flash('No candidates selected.', 'warning')
        return redirect(url_for('hr_dashboard'))
        
    status = 'Selected' if action == 'select' else 'Rejected'
    
    count = bulk_update_applications(app_ids, status, justification)
    flash(f'{count} candidates {status} with justification!', 'success')
    return redirect(url_for('hr_dashboard'))

@app.route('/hr/toggle_job/<job_id>')
def toggle_job(job_id):
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
        
    job = get_job_by_id(job_id)
    if job and str(job['hr_id']) == str(session['user_id']):
        new_status = 'Closed' if job['status'] == 'Open' else 'Open'
        update_job_status(job_id, new_status)
        flash(f'Job status updated to {new_status}.', 'success')
    else:
        flash('Unauthorized action.', 'error')
    
    return redirect(url_for('hr_dashboard'))

@app.route('/hr/view_resume/<resume_id>')
def view_resume(resume_id):
    if 'user_id' not in session or (session['role'] != 'hr' and session['role'] != 'admin'):
        return redirect(url_for('login'))
        
    resume = get_resume_by_id(resume_id)
    if resume:
        return render_template('view_resume.html', resume=resume)
    
    flash('Resume not found.', 'error')
    return redirect(url_for('hr_dashboard'))

@app.route('/files/resume/<path:filename>')
def get_resume_file(filename):
    """Serve resume files from data/uploads."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
# Security check: ensure the file is in data/uploads
    # We use basename to prevent directory traversal if something weird is passed
    filename = os.path.basename(filename)
    return send_from_directory('data/uploads', filename)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    stats = get_system_stats()
    all_jobs = get_all_jobs()
    activity = get_recent_activity()
    metrics = get_system_metrics()
    
    return render_template('admin_dashboard.html', stats=stats, users=stats['user_list'], jobs=all_jobs, activity=activity, metrics=metrics)

@app.route('/admin/delete_user/<user_id>')
def admin_delete_user(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    if delete_user(user_id):
        flash('User deleted successfully.', 'success')
    else:
        flash('Failed to delete user.', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_job/<job_id>')
def admin_delete_job(job_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
        
    if delete_job(job_id):
        flash('Job deleted successfully.', 'success')
    else:
        flash('Failed to delete job.', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/hr/bulk_upload/<job_id>', methods=['GET', 'POST'])
def bulk_upload_resumes(job_id):
    """Bulk upload and screen resumes for a job."""
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
    
    job = get_job_by_id(job_id)
    if not job or str(job['hr_id']) != str(session['user_id']):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('hr_dashboard'))
    
    if request.method == 'POST':
        if 'resume_zip' not in request.files:
            flash('No file uploaded.', 'error')
            return redirect(url_for('bulk_upload_resumes', job_id=job_id))
        
        zip_file = request.files['resume_zip']
        
        if zip_file.filename == '' or not zip_file.filename.endswith('.zip'):
            flash('Please upload a valid ZIP file.', 'error')
            return redirect(url_for('bulk_upload_resumes', job_id=job_id))
        
        try:
            # Extract and parse resumes
            resumes_data = extract_and_parse_resumes(zip_file)
            
            if not resumes_data:
                flash('No valid resumes found in ZIP file.', 'error')
                return redirect(url_for('bulk_upload_resumes', job_id=job_id))
            
            # Screen candidates
            scored_candidates = screen_candidates(job_id, resumes_data)
            
            # Save to candidate pool
            for candidate in scored_candidates:
                save_candidate_to_pool(job_id, candidate)
            
            flash(f'Successfully screened {len(scored_candidates)} candidates!', 'success')
            return redirect(url_for('view_screening_results', job_id=job_id))
            
        except Exception as e:
            flash(f'Error processing ZIP file: {str(e)}', 'error')
            return redirect(url_for('bulk_upload_resumes', job_id=job_id))
    
    return render_template('bulk_upload.html', job=job)

@app.route('/hr/screening_results/<job_id>')
def view_screening_results(job_id):
    """View screening results for a job."""
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
    
    job = get_job_by_id(job_id)
    if not job or str(job['hr_id']) != str(session['user_id']):
        flash('Unauthorized access.', 'error')
        return redirect(url_for('hr_dashboard'))
    
    candidates = get_candidate_pool(job_id)
    
    # Sort by score descending
    candidates.sort(key=lambda x: float(x.get('score', 0)), reverse=True)
    
    return render_template('screening_results.html', job=job, candidates=candidates)

@app.route('/hr/update_candidate/<candidate_id>', methods=['POST'])
def update_candidate(candidate_id):
    """Update HR decision for a candidate."""
    if 'user_id' not in session or session['role'] != 'hr':
        return redirect(url_for('login'))
    
    decision = request.form.get('decision')
    notes = request.form.get('notes', '')
    
    if update_candidate_decision(candidate_id, decision, notes):
        flash('Candidate decision updated.', 'success')
    else:
        flash('Failed to update decision.', 'error')
    
    # Get job_id from form to redirect back
    job_id = request.form.get('job_id')
    if job_id:
        return redirect(url_for('view_screening_results', job_id=job_id))
    return redirect(url_for('hr_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
