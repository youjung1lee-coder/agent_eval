"""Download pinned public quantized model with LFS SHA256 verification. No credentials."""
import hashlib
from pathlib import Path
import httpx

REPO = 'Qwen/Qwen2.5-0.5B-Instruct-GGUF'
REVISION = '9217f5db79a29953eb74d5343926648285ec7e67'
FILE = 'qwen2.5-0.5b-instruct-q4_k_m.gguf'


def main():
    destination = Path('.cache/models') / FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    metadata = httpx.get(f'https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true', timeout=30).json()
    info = next(x for x in metadata['siblings'] if x['rfilename'] == FILE)
    expected = info['lfs']['sha256']
    if destination.exists():
        with destination.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() == expected:
                print('Model already verified', expected)
                return
    temporary = destination.with_suffix('.partial')
    with httpx.stream('GET', f'https://huggingface.co/{REPO}/resolve/{REVISION}/{FILE}', follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        with temporary.open('wb') as f:
            for chunk in response.iter_bytes(1024 * 1024):
                f.write(chunk)
    with temporary.open('rb') as f:
        actual = hashlib.file_digest(f, 'sha256').hexdigest()
    if actual != expected:
        raise ValueError('Model SHA256 verification failed')
    temporary.replace(destination)
    print('Downloaded and verified', FILE, actual)


if __name__ == '__main__':
    main()
