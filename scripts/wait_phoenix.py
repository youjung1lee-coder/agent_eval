import time
import httpx

if __name__=="__main__":
    for _ in range(60):
        try:
            if httpx.get("http://127.0.0.1:6006/healthz",timeout=2).status_code==200:
                print("Phoenix ready")
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    else:
        raise SystemExit("Phoenix did not become ready in 60 seconds")
