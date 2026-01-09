import zipfile
import os

def zip_project(output_filename):
    # folders/files to exclude
    exclude_dirs = {'venv', '__pycache__', '.git', '.idea', '.vscode'}
    exclude_files = {output_filename, 'database.db'} # Exclude db if you want fresh start, but user might want it. Let's exclude db to be safe/small if they want fresh. Actually usually better to upload DB if they have data. But user said "clear storage" previously so maybe fresh. Let's include DB but warn? No, let's include DB as it might have the admin user.
    # Actually, exclude DB to avoid conflicts if they want a fresh start, but if they want to keep data... 
    # Let's include DB, it's sqlite, usually small unless heavy usage.
    # Exclude venv is the critical part.

    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file == output_filename:
                    continue
                if file.endswith('.pyc'):
                    continue
                    
                file_path = os.path.join(root, file)
                # print(f"Zipping {file_path}")
                zipf.write(file_path, arcname=os.path.relpath(file_path, '.'))

if __name__ == '__main__':
    zip_project('hr_app_deploy.zip')
    print("Created hr_app_deploy.zip successfully!")
