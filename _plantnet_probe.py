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

for url in urls:
    try:
        resp = requests.post(url, params=params, files=files, data=data, timeout=20)
        body = resp.text.replace("\n", " ").replace("\r", " ")[:200]
        print(f"{url:<45} {resp.status_code!s:<8} {body}")
    except Exception as e:
        print(f"{url:<45} {'ERROR':<8} {str(e)[:200]}")
