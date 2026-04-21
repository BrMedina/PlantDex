import base64
import requests

url = "https://my-api.plantnet.org/v2/identify/all"
params = {"api-key": "2b10ILRlTzEqhJPfKqQ8cuN5", "lang": "en"}
png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7ZPioAAAAASUVORK5CYII="
png_bytes = base64.b64decode(png_b64)

for organs in ["leaf", "auto"]:
    files = {"images": ("pixel.png", png_bytes, "image/png")}
    data = {"organs": organs}
    try:
        r = requests.post(url, params=params, files=files, data=data, timeout=30)
        print(f"organs={organs}")
        print(f"status={r.status_code}")
        print(r.text)
    except Exception as e:
        print(f"organs={organs}")
        print("status=ERROR")
        print(str(e))
    print("-" * 80)
