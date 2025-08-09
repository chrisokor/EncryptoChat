import base64

def bytes_to_base64_str(bytes_input: bytes) -> str:
    return base64.b64encode(bytes_input).decode()

def base64_str_to_bytes(str_input: str) -> bytes:
    return base64.b64decode(str_input.encode())

