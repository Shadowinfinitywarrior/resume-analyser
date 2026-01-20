import os
import shutil
import csv

DATA_DIR = 'data'
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')

CSV_HEADERS = {
    'users.csv': ['id', 'username', 'email', 'password', 'role'],
    'jobs.csv': ['id', 'hr_id', 'title', 'description', 'skills_required', 'vacancies', 'status'],
    'resumes.csv': ['id', 'user_id', 'filename', 'content_text', 'upload_date', 'file_path'],
    'applications.csv': ['id', 'job_id', 'user_id', 'resume_id', 'status', 'hr_notes', 'score', 'eligibility'],
    'candidate_pool.csv': ['id', 'job_id', 'filename', 'content_text', 'score', 'recommendation', 'justification', 'hr_decision', 'upload_date', 'file_path']
}

def clear_data():
    print("🧹 Clearing all application data...")
    
    # Clear CSV files
    for filename, headers in CSV_HEADERS.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            print(f"✅ Cleared {filename}")

    # Clear uploads
    if os.path.exists(UPLOADS_DIR):
        for item in os.listdir(UPLOADS_DIR):
            item_path = os.path.join(UPLOADS_DIR, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"❌ Failed to delete {item_path}: {e}")
        print("✅ Cleared uploads directory")
    
    print("✨ Reset complete!")

if __name__ == "__main__":
    clear_data()
