import os

OUTPUT_FILE = "project_structure.txt"
EXCLUDED_DIRS = {'.git', '.next', 'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build'}
EXCLUDED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.xlsx', '.xls', '.db'}

def export_project_structure():
    print("פותח סריקה של מבנה הפרויקט...")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("=== Project Structure and File Contents ===\n\n")
        
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            
            relative_path = os.path.relpath(root, '.')
            indent = relative_path.count(os.sep) if relative_path != '.' else 0
            indent_str = '    ' * indent
            
            if relative_path != '.':
                f.write(f"{indent_str}📁 {os.path.basename(root)}/\n")
                
            for file in files:
                if any(file.endswith(ext) for ext in EXCLUDED_EXTENSIONS):
                    continue
                    
                file_path = os.path.join(root, file)
                f.write(f"{indent_str}    📄 {file}\n")
                
                if file.endswith(('.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.html', '.css', '.md')):
                    f.write(f"{indent_str}    --- BEGIN CONTENT OF {file} ---\n")
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as cf:
                            content = cf.read()
                            for line in content.splitlines():
                                f.write(f"{indent_str}        {line}\n")
                    except Exception as e:
                        f.write(f"{indent_str}        [Error reading file: {e}]\n")
                    f.write(f"{indent_str}    --- END CONTENT ---\n\n")

    print(f"\nהקובץ נוצר בהצלחה!")
    print(f"📁 שם הקובץ שנשמר בתיקייה הראשית: {OUTPUT_FILE}")

if __name__ == "__main__":
    export_project_structure()