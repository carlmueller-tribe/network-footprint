from urllib.parse import urlparse

# url() here is NOT a Django route
url = "https://example.com"
parsed_url = urlparse(url)
image_url = "https://cdn.example.com/img.png"
