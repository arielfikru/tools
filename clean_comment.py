#!/usr/bin/env python3
"""
Code Comment Cleaner - Menghapus komentar inline atau semua komentar dari file kode sumber
"""

import os
import re
import sys # Dihapus jika tidak ada penggunaan sys lainnya
import argparse
from pathlib import Path

# Definisi pola komentar untuk berbagai jenis bahasa/gaya
COMMENT_DEFINITIONS = {
    'python_like': {
        'inline': [r'(^[^#\n]*)([ \t]+#[^\n]*$)'],  # Kode di group(1), komentar di group(2)
        'full_line': [r'^\s*#.*$'], # Baris penuh komentar '#'
        # Tidak ada 'block_dotall' untuk Python standar (# tidak membentuk blok multiline)
        # """docstrings""" atau '''strings''' sengaja tidak dihapus karena bisa jadi kode valid.
    },
    'c_like': { # Untuk JS, Java, C, C++, C#, Kotlin, Swift, TS, Go, Rust, dll.
        'inline': [
            r'(^[^/\n]*)([ \t]+//[^\n]*$)',                 # // komentar
            r'(^[^/\n]*)([ \t]+/\*.*?\*/[ \t]*$)',          # /* inline blok */ setelah kode
        ],
        'full_line': [
            r'^\s*//.*$',                                  # Baris penuh // komentar
            r'^\s*/\*.*?\*/\s*$',                          # Baris penuh /* blok */
        ],
        'block_dotall': r'/\*.*?\*/',                       # Untuk /* ... */ multi-baris
    },
    'c_like_line_only': { # Untuk Go, Rust (hanya //)
        'inline': [r'(^[^/\n]*)([ \t]+//[^\n]*$)'],
        'full_line': [r'^\s*//.*$'],
        'block_dotall': None, # Tidak ada komentar blok multi-baris standar dengan //
    },
    'xml_like': { # Untuk XML, HTML
        'inline': [r'(^[^<\n]*)([ \t]+<!--.*?-->[ \t]*$)'], # <!-- inline --> setelah kode
        'full_line': [r'^\s*<!--.*?-->\s*$'],              # Baris penuh <!-- komentar -->
        'block_dotall': r'<!--.*?-->',                     # Untuk <!-- ... --> multi-baris
    },
    'css_like': { # CSS hanya /* */
        'inline': [r'(^[^/\n]*)([ \t]+/\*.*?\*/[ \t]*$)'],
        'full_line': [r'^\s*/\*.*?\*/\s*$'],
        'block_dotall': r'/\*.*?\*/',
    },
    'php_like': { # PHP mendukung //, #, /* */
        'inline': [
            r'(^[^/\n#]*)([ \t]+//[^\n]*$)',
            r'(^[^/\n#]*)([ \t]+#[^\n]*$)', # Pastikan tidak bentrok dengan // atau /*
            r'(^[^/\n#]*)([ \t]+/\*.*?\*/[ \t]*$)',
        ],
        'full_line': [
            r'^\s*//.*$',
            r'^\s*#.*$',
            r'^\s*/\*.*?\*/\s*$',
        ],
        'block_dotall': r'/\*.*?\*/', # Hanya /* */ yang block dotall
    },
}

# Pemetaan ekstensi file ke definisi komentar yang sesuai
LANGUAGE_MAP = {
    # Python & Hash-based
    '.py': COMMENT_DEFINITIONS['python_like'],
    '.sh': COMMENT_DEFINITIONS['python_like'], # Shell script menggunakan #
    '.rb': COMMENT_DEFINITIONS['python_like'], # Ruby menggunakan #
    '.yml': COMMENT_DEFINITIONS['python_like'], # YAML menggunakan #
    '.yaml': COMMENT_DEFINITIONS['python_like'],# YAML menggunakan #

    # C-like (mendukung // dan /* */)
    '.js': COMMENT_DEFINITIONS['c_like'],
    '.java': COMMENT_DEFINITIONS['c_like'],
    '.c': COMMENT_DEFINITIONS['c_like'],
    '.cpp': COMMENT_DEFINITIONS['c_like'],
    '.cs': COMMENT_DEFINITIONS['c_like'],
    '.kts': COMMENT_DEFINITIONS['c_like'], # Kotlin Script
    '.kt': COMMENT_DEFINITIONS['c_like'],  # Kotlin
    '.swift': COMMENT_DEFINITIONS['c_like'],
    '.ts': COMMENT_DEFINITIONS['c_like'],  # TypeScript
    '.jsx': COMMENT_DEFINITIONS['c_like'], # JSX
    '.tsx': COMMENT_DEFINITIONS['c_like'], # TSX
    # JSON dengan komentar (non-standar, tapi umum di JSONC/JSON5)
    '.json': COMMENT_DEFINITIONS['c_like'],

    # C-like line comments only (//)
    '.go': COMMENT_DEFINITIONS['c_like_line_only'],   # Go
    '.rs': COMMENT_DEFINITIONS['c_like_line_only'],   # Rust

    # XML/HTML-like
    '.xml': COMMENT_DEFINITIONS['xml_like'],
    '.html': COMMENT_DEFINITIONS['xml_like'],

    # CSS-like
    '.css': COMMENT_DEFINITIONS['css_like'],

    # PHP-like
    '.php': COMMENT_DEFINITIONS['php_like'],
}


def _remove_comments_universal(content, lang_def, remove_all):
    """Fungsi inti untuk menghapus komentar berdasarkan definisi bahasa dan flag."""
    processed_content = content

    # Tahap 1: Hapus komentar blok multi-baris (hanya jika remove_all)
    if remove_all:
        block_pattern_dotall = lang_def.get('block_dotall')
        if block_pattern_dotall:
            # PERINGATAN: Regex sederhana untuk komentar blok dapat secara tidak sengaja
            # menghapus kode jika string literal berisi penanda komentar blok.
            processed_content = re.sub(block_pattern_dotall, '', processed_content, flags=re.DOTALL)

    lines = processed_content.split('\n')
    result_lines = []

    for line_text in lines:
        modified_line = line_text

        if remove_all:
            # Tahap 2a (remove_all): Cek apakah *seluruh baris yang tersisa* adalah komentar baris penuh
            is_full_line_comment_type = False
            for pattern_str in lang_def.get('full_line', []):
                if re.fullmatch(pattern_str, modified_line.strip()):
                    is_full_line_comment_type = True
                    break
            if is_full_line_comment_type:
                result_lines.append("")  # Ganti baris komentar penuh dengan baris kosong
                continue # Lanjut ke baris berikutnya

        # Tahap 2b: Hapus komentar inline (setelah kode) atau semua sisa komentar di baris (jika remove_all)
        temp_line_for_inline = modified_line
        # Iteratif terapkan semua pola inline sampai tidak ada perubahan.
        previous_state_before_inline_loop = ""
        while previous_state_before_inline_loop != temp_line_for_inline:
            previous_state_before_inline_loop = temp_line_for_inline
            for pattern_str in lang_def.get('inline', []):
                match = re.match(pattern_str, temp_line_for_inline) # Gunakan temp_line_for_inline yang terus update
                if match:
                    code_part = match.group(1)
                    # comment_part = match.group(2) # Untuk debugging

                    if remove_all:
                        # Dalam mode --all, jika pola inline cocok, selalu ambil bagian kode.
                        # rstrip() akan membersihkan whitespace. Jika code_part jadi "", baris jadi kosong.
                        temp_line_for_inline = code_part.rstrip()
                    elif code_part.strip(): # Mode inline-only: hanya proses jika ada kode *sebelum* komentar
                        temp_line_for_inline = code_part.rstrip()
                    # Jika bukan remove_all dan tidak ada code_part.strip(),
                    # berarti komentar tidak didahului kode, jadi biarkan (temp_line_for_inline tidak berubah).
                    # Ini akan menghentikan loop while jika hanya kasus itu yang tersisa.
        
        modified_line = temp_line_for_inline
        result_lines.append(modified_line)

    # Pembersihan baris tambahan jika remove_all aktif
    if remove_all:
        # 1. Ganti baris yang hanya berisi whitespace menjadi benar-benar kosong
        cleaned_stage1 = [line if line.strip() else "" for line in result_lines]
        
        # 2. Hapus baris kosong berurutan (sisakan maksimal satu, kecuali file jadi kosong total)
        cleaned_stage2 = []
        if cleaned_stage1: # Hanya proses jika ada baris
            for i, line_text in enumerate(cleaned_stage1):
                if line_text != "": # Jika baris tidak kosong (setelah strip di atas)
                    cleaned_stage2.append(line_text)
                elif not cleaned_stage2 or cleaned_stage2[-1] != "":
                    # Tambah baris kosong jika list hasil kosong (awal file) atau baris sebelumnya tidak kosong
                    cleaned_stage2.append("") 
            
            # 3. Hapus baris kosong di awal dan akhir (kecuali jika itu satu-satunya baris)
            if cleaned_stage2:
                while cleaned_stage2 and cleaned_stage2[0] == "":
                    cleaned_stage2.pop(0)
                if cleaned_stage2: # Cek lagi karena bisa jadi kosong
                    while len(cleaned_stage2) > 1 and cleaned_stage2[-1] == "":
                        cleaned_stage2.pop()
        result_lines = cleaned_stage2

    final_content = "\n".join(result_lines)

    # Penanganan newline akhir untuk mencerminkan file asli
    original_had_trailing_newline = content.endswith('\n')
    
    # Kasus khusus: jika input adalah "\n" dan output jadi "", kembalikan "\n"
    if not final_content and not result_lines and content == "\n":
         return "\n"
    # Kasus khusus: jika input "" dan output "", kembalikan ""
    if not final_content and not result_lines and not content:
        return ""

    if final_content: # Ada konten hasil
        if original_had_trailing_newline:
            if not final_content.endswith('\n'):
                final_content += '\n'
        else: # original tidak punya trailing newline
            if final_content.endswith('\n'):
                final_content = final_content.rstrip('\n')
    elif original_had_trailing_newline : # Hasilnya kosong (misal dari `\n`.join([""])), tapi asli punya newline
        final_content = "\n" # Ini berarti file yang tadinya berisi komentar saja, jadi file kosong dengan newline
    # Jika final_content kosong dan original_had_trailing_newline false, maka final_content sudah benar ("")
    
    return final_content

def process_code_content(content, file_extension, remove_all_comments_flag):
    """
    Wrapper untuk _remove_comments_universal, mendapatkan definisi bahasa.
    """
    lang_def = LANGUAGE_MAP.get(file_extension.lower())
    if not lang_def:
        # Tidak ada definisi komentar untuk tipe file ini, jadi tidak ada yang bisa dilakukan.
        # Bisa juga print warning jika diperlukan.
        return content
    return _remove_comments_universal(content, lang_def, remove_all_comments_flag)

def process_file(file_path, dry_run=False, remove_all_comments=False):
    """Proses satu file, hapus komentar inline atau semua komentar"""
    file_path = Path(file_path) # Pastikan ini objek Path
    file_extension = file_path.suffix # Path.suffix sudah termasuk '.'
    
    if file_extension.lower() not in LANGUAGE_MAP:
        print(f"Skipping {file_path} (unsupported file type or no comment definition)")
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_content = process_code_content(content, file_extension, remove_all_comments)
        
        if content != new_content:
            if dry_run:
                print(f"Would modify: {file_path}")
                # Untuk debugging dry-run yang lebih detail:
                # import difflib
                # diff = difflib.unified_diff(content.splitlines(), new_content.splitlines(),
                #                             fromfile=str(file_path), tofile="modified", lineterm='')
                # print('\n'.join(diff))
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Modified: {file_path}")
        else:
            print(f"No changes needed: {file_path}")
    except UnicodeDecodeError:
        print(f"Skipping {file_path} (not a text file or encoding issues)")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def process_path(path_to_process, dry_run=False, remove_all_comments=False):
    """Proses file atau direktori (rekursif untuk direktori)"""
    path_obj = Path(path_to_process)
    
    if path_obj.is_file():
        process_file(path_obj, dry_run, remove_all_comments)
    elif path_obj.is_dir():
        print(f"Processing directory: {path_obj}")
        for item in path_obj.rglob('*'): # rglob untuk rekursif
            if item.is_file():
                process_file(item, dry_run, remove_all_comments)
    else:
        print(f"Path not found or not a file/directory: {path_obj}")

def main():
    parser = argparse.ArgumentParser(
        description="Clean inline comments (default) or all comments from code files."
    )
    parser.add_argument("paths", nargs='+', help="Files or directories to process")
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Remove all comments (including full-line and multi-line blocks), not just inline ones."
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    for path_arg in args.paths:
        process_path(path_arg, args.dry_run, args.all)

if __name__ == "__main__":
    main()