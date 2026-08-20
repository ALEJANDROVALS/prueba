import time
import threading
import requests
from fastapi import FastAPI, Response, Query, Request
from fastapi.responses import RedirectResponse

app = FastAPI(title="IPTV Live Proxy API")

BASE_URL = "https://workers.dev"

# Estructura para guardar la lista de películas fija (Título, portada, url interna)
cached_movies = []
last_list_update = 0
CACHE_DURATION = 86400  # Actualizar la lista de películas solo una vez al día (24 horas)
lock = threading.Lock()

def update_movie_list():
    """Descubre películas y guarda sus metadatos fijos en caché."""
    global cached_movies, last_list_update
    if not lock.acquire(blocking=False):
        return

    try:
        temp_movies = []
        max_pages = 3  # Puedes subir esto si quieres más películas

        for page in range(1, max_pages + 1):
            try:
                res = requests.get(f"{BASE_URL}/list", params={"page": page}, timeout=10)
                res.raise_for_status()
                data = res.json()
            except Exception:
                continue

            peliculas = data.get("featured", []) + data.get("movies", [])
            for item in peliculas:
                movie_url = item.get("url") or item.get("link")
                title = item.get("title") or item.get("name")
                poster = item.get("poster") or item.get("image") or ""
                
                if movie_url and title:
                    # Guardamos solo los datos fijos
                    temp_movies.append({
                        "title": title,
                        "poster": poster,
                        "url": movie_url
                    })

        if temp_movies:
            cached_movies = temp_movies
            last_list_update = time.time()
    finally:
        lock.release()

@app.get("/playlist.m3u")
def get_playlist(request: Request):
    """Genera el archivo M3U apuntando los enlaces de reproducción a esta misma API."""
    global last_list_update
    
    # Si la caché está vacía o expiró (24h), lanzar actualización en segundo plano
    if not cached_movies or (time.time() - last_list_update > CACHE_DURATION):
        threading.Thread(target=update_movie_list, daemon=True).start()
    
    if not cached_movies:
        return Response(
            content="#EXTM3U\n#INFO: Construyendo base de datos por primera vez. Regresa en 10 segundos...",
            media_type="application/x-mpegurl"
        )

    # Construir la URL base de tu servidor en Render de forma dinámica
    base_server_url = str(request.base_url).rstrip("/")

    m3u_lines = ["#EXTM3U"]
    for movie in cached_movies:
        extinf = f'#EXTINF:-1 tvg-logo="{movie["poster"]}" group-title="ZonaAPI", {movie["title"]}'
        # El enlace de reproducción ahora apunta a tu endpoint interno '/play'
        proxy_play_url = f'{base_server_url}/play?url={requests.utils.quote(movie["url"])}'
        m3u_lines.append(f"{extinf}\n{proxy_play_url}")

    return Response(content="\n".join(m3u_lines), media_type="application/x-mpegurl")

@app.get("/play")
def play_movie(url: str = Query(..., description="URL original de la película para extraer")):
    """Intercepta la reproducción, extrae el enlace dinámico al momento y redirige."""
    try:
        # Petición en tiempo real al extractor original
        ext_res = requests.get(f"{BASE_URL}/extract", params={"url": url}, timeout=8)
        ext_res.raise_for_status()
        movie_data = ext_res.json()

        streams = movie_data.get("streams", [])
        if streams:
            # Obtenemos el archivo .tar / .m3u8 con el r_range actualizado en este preciso instante
            real_stream_url = streams[0].get("file") or streams[0].get("url") or streams[0].get("link")
            if real_stream_url:
                # Redirección HTTP 302: el reproductor IPTV seguirá este enlace de inmediato
                return RedirectResponse(url=real_stream_url, status_code=302)
                
    except Exception as e:
        print(f"Error al extraer en tiempo real: {e}")
    
    # Si falla, retornar un error 404 para que el reproductor sepa que no está disponible
    return Response(content="No se pudo obtener el stream en tiempo real", status_code=404)

@app.get("/")
def index():
    return {"status": "online", "mode": "Proxy en tiempo real activo"}
