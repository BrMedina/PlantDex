import requests

urls = [
    "https://my-api.plantnet.org/v2/identify/all",
    "https://my-api.plantnet.org/v2/identify",
    "https://my-api.plantnet.org/v1/identify/all",
    "https://my-api.plantnet.org/v1/identify",
    "https://api.plantnet.org/v1/identify",
    "https://api.plantnet.org/v1/identify/all",
]
params = {"api-key": "2b10ILRlTzEqhJPfKqQ8cuN5", "lang": "en"}
files = {"images": ("x.jpg", b"123", "image/jpeg")}
data = {"organs": "leaf"}

print(f"{'URL':<45} {'STATUS':<8} EXCERPT")
print("-" * 120)
for u in urls:
    try:
        r = requests.post(u, params=params, files=files, data=data, timeout=3)
        t = r.text.replace("\n", " ").replace("\r", " ")[:200]
        print(f"{u:<45} {r.status_code:<8} {t}")
    except Exception as e:
        print(f"{u:<45} {'ERROR':<8} {str(e)[:200]}")
