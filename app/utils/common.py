import os
from typing import Dict, Any, List
import json

def ensure_directory_exists(directory_path: str) -> None:
    """
    Belirtilen dizinin var olduğundan emin olur, yoksa oluşturur.
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

def save_json_to_file(data: Dict[str, Any], file_path: str) -> str:
    """
    Veriyi JSON formatında dosyaya kaydeder.
    """
    directory = os.path.dirname(file_path)
    ensure_directory_exists(directory)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return file_path

def load_json_from_file(file_path: str) -> Dict[str, Any]:
    """
    Dosyadan JSON verisini okur.
    """
    if not os.path.exists(file_path):
        return {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_file_size(size_in_bytes: int) -> str:
    """
    Dosya boyutunu okunabilir formata dönüştürür.
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} TB"
