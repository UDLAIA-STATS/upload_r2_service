def calculate_upload_timeout(total_size: int) -> int:
    """Versión para usuarios con internet muy lento (0.5 Mbps)"""
    max_size = 5 * 1024 * 1024 * 1024
    total_size = min(total_size, max_size)

    size_mbits = (total_size * 8) / (1024 * 1024)
    base_seconds = size_mbits / 0.5  # 0.5 Mbps mínimo

    timeout_seconds = int(base_seconds * 1.8)  # 80% margen adicional

    return max(600, min(14400, timeout_seconds))