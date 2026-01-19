def calculate_upload_timeout(total_size: int) -> int:
    """
    Calcula un timeout de subida asumiendo conexiones muy lentas (~0.5 Mbps).

    - 0.5 Mbps se usa como velocidad mínima conservadora para usuarios con
      conexiones inestables (p.ej. redes móviles en zonas rurales). Esto
      garantiza que incluso en esos casos el timeout sea suficiente.
    - Se aplica un margen del 80 % sobre el tiempo teórico para cubrir
      variaciones de red, pausas breves y sobrecostes de protocolo (TLS,
      reintentos, cabeceras, etc.).
    - El resultado se acota entre 600 s (10 minutos) y 14 400 s (4 horas)
      para evitar timeouts demasiado cortos o esperas excesivas en la
      interfaz de usuario.
    """
    max_size = 5 * 1024 * 1024 * 1024
    total_size = min(total_size, max_size)

    # Convertimos el tamaño total a megabits para estimar el tiempo teórico
    # de subida en función de la velocidad mínima esperada (0.5 Mbps).
    size_mbits = (total_size * 8) / (1024 * 1024)
    base_seconds = size_mbits / 0.5  # 0.5 Mbps como punto de diseño para "internet muy lento"

    # Multiplicamos por 1.8 (80 % extra) para añadir un margen amplio frente a:
    # - fluctuaciones de ancho de banda,
    # - sobrecarga de protocolo y cifrado,
    # - pequeños cortes o reintentos de conexión.
    timeout_seconds = int(base_seconds * 1.8)

    # Restringimos el timeout entre 10 minutos y 4 horas para equilibrar:
    # - fiabilidad en subidas grandes en conexiones lentas,
    # - con una experiencia de usuario razonable y límites operativos.
    return max(600, min(14400, timeout_seconds))