import os

def is_allowed_path(path, banned_prefixes):
    """Check if a directory path is allowed based on prefixes."""
    path_parts = path.split(os.sep)
    for part in path_parts:
        for prefix in banned_prefixes:
            if part.startswith(prefix):
                return False
    return True

def is_allowed_file(filename, banned_extensions):
    """Check if a file is allowed based on its extension."""
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext not in banned_extensions

def read_file_content(file_path, max_size_kb=256):
    """
    Read and return the content of a file if its size is within the max size limit.
    Returns None if the file exceeds the size limit.
    """
    # Cek ukuran file dalam KB
    file_size_kb = os.path.getsize(file_path) / 1024
    
    # Skip jika ukuran file melebihi batas maksimum
    if file_size_kb > max_size_kb:
        return None
        
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
            return file.read()
    except:
        return "Unable to read file content - might be a binary file."

def generate_report(folder_path, banned_prefixes, banned_extensions, max_size_kb=256):
    """
    Scan a folder recursively and generate a report of all allowed files.
    """
    report = []
    skipped_files = []
    
    for root, dirs, files in os.walk(folder_path):
        # Skip directories with banned prefixes
        dirs[:] = [d for d in dirs if is_allowed_path(d, banned_prefixes)]
        
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, folder_path)
            
            if is_allowed_file(file, banned_extensions):
                content = read_file_content(file_path, max_size_kb)
                
                if content is None:
                    # File melebihi ukuran maksimum
                    file_size_kb = os.path.getsize(file_path) / 1024
                    skipped_files.append(f"{relative_path} ({file_size_kb:.2f} KB)")
                else:
                    report.append(f"{relative_path}\n```\n{content}\n```\n")
    
    # Tambahkan informasi tentang file yang diskip di akhir laporan
    if skipped_files:
        report.append("\n## Files Skipped (Size > 256KB)\n")
        for skipped in skipped_files:
            report.append(f"- {skipped}")
    
    return "\n".join(report)

def main():
    folder_path = input("Masukkan path folder yang ingin dipindai: ")
    
    # Validasi path
    if not os.path.exists(folder_path):
        print(f"Error: Path '{folder_path}' tidak ditemukan.")
        return
    
    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' bukan folder.")
        return
    
    # Menentukan file output
    output_file = f"{folder_path}.md"
    
    # Daftar ekstensi dan prefix yang dilarang
    banned_extensions = [
        "jpg", "png", "jpeg", "webp", "ico", "gif", "bmp", "tiff", "svg",
        "pdf", "zip", "rar", "7z", "tar", "gz", 
        "exe", "dll", "so", "dylib", "bin", "dat", "db", "sqlite",
        "mp3", "mp4", "avi", "mov", "wmv", "flv", "mkv", "wav", "aac", "ogg",
        "doc", "docx", "xls", "xlsx", "ppt", "pptx"
    ]
    
    banned_prefixes = ["."]
    
    # Ukuran maksimum file (dalam KB)
    max_size_kb = 256
    
    # Generate report
    print(f"Memindai folder '{folder_path}'...")
    print(f"File dengan ukuran > {max_size_kb}KB akan dilewati.")
    report = generate_report(folder_path, banned_prefixes, banned_extensions, max_size_kb)
    
    # Menyimpan report ke file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"Report berhasil disimpan di '{output_file}'")

if __name__ == "__main__":
    main()