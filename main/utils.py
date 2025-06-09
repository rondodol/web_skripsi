# main/utils.py

def normalize_platform(input_str: str) -> str:
    """
    Fungsi dummy untuk men‐normalize nama platform.
    Saat ini hanya mengembalikan input dalam huruf kecil,
    tanpa spasi tambahan. 
    Nanti, jika sudah punya daftar alias, Anda bisa memperluasnya.
    """
    return input_str.strip().lower()

def hybrid_recommend(user_id, genre_list, platform_list):
    # Dummy data untuk uji coba (sementara)
    return [
        {"name": "Minecraft", "genre": "Adventure", "platform": "pc"},
        {"name": "Super Mario", "genre": "Platformer", "platform": "nintendo switch"},
    ]
